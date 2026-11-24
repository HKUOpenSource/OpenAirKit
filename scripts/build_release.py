"""Produce a verified Linux ARM64 application archive from this checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jetson_release, monitor_release, release_tools


def build(platform, output):
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Release output must be a new directory: " + str(output))
    app = ROOT / "apps" / ("jetson-console" if platform == "jetson" else "spark-console")
    subprocess.run(["npm", "--prefix", str(app / "frontend"), "run", "build"], check=True)
    output.mkdir(parents=True)
    stage = output / "stage"
    if platform == "jetson":
        wheels = output / "wheels"
        release_tools.download_wheels(wheels, app / "requirements-jetson.lock", platform)
        jetson_release.build(stage, wheels)
        subprocess.run([sys.executable, str(stage / "deploy/manage.py"), "verify", "--stage", str(stage)], check=True, stdout=subprocess.DEVNULL)
    else:
        monitor_release.stage(stage)
        monitor_release.download(stage)
        monitor_release.verify(stage)
    target = release_tools.archive(stage, output, platform)
    print(json.dumps({"archive": str(target), "checksum": str(target) + ".sha256"}))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("jetson", "spark"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.platform, args.output)
