"""Build a content-addressed, data-only Jetson V2 offline release."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def build(output, wheels):
    source = ROOT / "apps/jetson-console"
    if output.exists():
        raise ValueError("Output must be a new directory")
    if not (source / "frontend/dist/index.html").exists():
        raise ValueError("Build the V2 frontend first")
    if not wheels.is_dir() or not list(wheels.glob("*.whl")):
        raise ValueError("Offline ARM64 CPython 3.10 wheels are required")
    output.mkdir(parents=True)
    (output / "backend").mkdir()
    shutil.copytree(source / "backend/aoc_jetson", output / "backend/aoc_jetson",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(source / "frontend/dist", output / "frontend")
    shutil.copytree(ROOT / "deploy/jetson", output / "deploy")
    shutil.copyfile(source / "requirements-jetson.lock", output / "requirements.lock")
    shutil.copyfile(ROOT / "config/jetson.example.json", output / "device.example.json")
    shutil.copytree(wheels, output / "wheels")
    (output / "RELEASE-VERSION").write_text("0.3.0\n")
    (output / "THIRD_PARTY_NOTICES.md").write_text("Dependencies are supplied from the locked offline wheelhouse.\n")
    (output / "THIRD_PARTY_DEPENDENCIES.json").write_text(json.dumps({"platform":"jetson","lock":"requirements.lock","wheelhouse":True}, indent=2) + "\n")
    (output / "THIRD_PARTY_LICENSES").mkdir()
    (output / "THIRD_PARTY_LICENSES/README.txt").write_text("See the locked wheelhouse metadata for dependency licenses.\\n")
    files = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob("*")) if path.is_file()}
    release = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {"release": release,
                "git_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
                "architecture": "aarch64", "python": "3.10", "product": "agentic-ocudu-jetson",
                "files": files}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"release": release, "path": str(output), "files": len(files),
                      "manifest_sha256": hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    arguments = parser.parse_args()
    build(arguments.output, arguments.wheels)
