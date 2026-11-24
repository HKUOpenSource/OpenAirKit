from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
json.loads((root / "config/images.lock.json").read_text())
license_path = root / "LICENSE"
if not license_path.is_file():
    raise SystemExit("missing root LICENSE file")
license_text = license_path.read_text(encoding="utf-8")
if "Apache License" not in license_text or "Version 2.0" not in license_text:
    raise SystemExit("root LICENSE must contain Apache License 2.0")
citation_path = root / "CITATION.cff"
if not citation_path.is_file() or not citation_path.read_text(encoding="utf-8").strip():
    raise SystemExit("missing root CITATION.cff file")
for package in (root / "apps").glob("*/frontend/package.json"):
    data = json.loads(package.read_text())
    if not data.get("private"):
        raise SystemExit(f"frontend package must remain private: {package}")
print("License and package ownership audit passed")
