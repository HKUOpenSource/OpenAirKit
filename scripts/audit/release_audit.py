"""Static release-boundary audit; generated releases are verified by managers."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
for path in (root / "apps/jetson-console/requirements-jetson.lock", root / "apps/spark-platform/requirements-spark.lock"):
    if not path.exists() or not path.read_text().strip():
        raise SystemExit(f"missing locked dependency file: {path}")
for path in (root / "deploy/jetson", root / "deploy/spark/platform"):
    if any(p.is_symlink() for p in path.rglob("*")):
        raise SystemExit(f"symlink in deployment tree: {path}")
for name in ("config/network-contract.json", "config/images.lock.json"):
    json.loads((root / name).read_text())
print("Release boundary audit passed")
