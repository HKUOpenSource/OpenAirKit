"""Static release-boundary audit; generated releases are verified by managers."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
for path in (root / "apps/jetson-console/requirements-jetson.lock", root / "apps/spark-console/requirements-spark.lock"):
    if not path.exists() or not path.read_text().strip():
        raise SystemExit(f"missing locked dependency file: {path}")
for path in (root / "deploy/jetson", root / "deploy/spark/platform"):
    if any(p.is_symlink() for p in path.rglob("*")):
        raise SystemExit(f"symlink in deployment tree: {path}")
for name in ("config/network-contract.json", "config/images.lock.json"):
    json.loads((root / name).read_text())
stack = root / 'deploy/spark/stack'
for name in ('runtime.py', 'package.py', 'systemd/aoc-v2-core.service', 'systemd/aoc-v2-radio.service'):
    if not (stack / name).is_file() or (stack / name).is_symlink():
        raise SystemExit('missing current stack deployment input: ' + name)
if 'scripts.v2' in (root / 'scripts/aocctl').read_text():
    raise SystemExit('stack CLI imports a retired implementation')
for name in ('aoc-v2-core.service', 'aoc-v2-radio.service'):
    text = (stack / 'systemd' / name).read_text()
    if '[Install]' in text or '/opt/agentic-ocudu/v2/' not in text:
        raise SystemExit('stack unit violates independent installation contract: ' + name)
print("Release boundary audit passed")
