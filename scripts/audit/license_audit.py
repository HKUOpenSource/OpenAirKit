from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
json.loads((root / "config/images.lock.json").read_text())
if (root / "LICENSE").exists():
    raise SystemExit("public LICENSE is not approved for this internal project")
for package in (root / "apps").glob("*/frontend/package.json"):
    data = json.loads(package.read_text())
    if not data.get("private"):
        raise SystemExit(f"frontend package must remain private: {package}")
print("License and package ownership audit passed")
