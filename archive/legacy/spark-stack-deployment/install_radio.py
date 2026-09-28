#!/usr/bin/env python3
"""Install a reviewed independent radio package. Never starts or stops the legacy radio."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.aoclib.core import write_json
from scripts.aoclib.radio import digest, validate_profile
from scripts.aoclib.cli import compose_args


INSTALL = Path("/opt/agentic-ocudu")
CONFIG = Path("/etc/agentic-ocudu")
UNITS = ("aoc-stack.target", "aoc-core.service", "aoc-gnb.service")
LAUNCHER = Path("/home/defaultuser/.local/bin/oai-spark-services.sh")
LAUNCHER_SHA = "aa1b71c83594e7a9a6dd52c1997a2f0eaf124a330e50ed93c34bd1f6a47ab2cc"


def verify_stage(stage):
    manifest = json.loads((stage / "release.json").read_text())
    release = stage / "release"
    if any(path.is_symlink() for path in stage.rglob("*")):
        raise ValueError("Staged package contains a symlink")
    actual = {str(path.relative_to(release)): digest(path) for path in sorted(release.rglob("*")) if path.is_file()}
    if actual != manifest["files"]:
        raise ValueError("Staged release checksum mismatch")
    expected = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()[:16]
    if manifest["release_id"] != expected:
        raise ValueError("Staged release identifier mismatch")
    validate_profile(json.loads((stage / "radio.json").read_text()), serial_required=False)
    compose_args(json.loads((stage / "spark.json").read_text()), stage / "core")
    return manifest


def install(stage):
    manifest = verify_stage(stage)
    if os.geteuid() != 0:
        raise ValueError("Install from an administrator terminal with sudo")
    if digest(LAUNCHER) != LAUNCHER_SHA:
        raise ValueError("Original launcher differs from the reviewed baseline")
    for unit in ("aoc-stack.target", "aoc-gnb.service"):
        state = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True).stdout.strip()
        if state not in ("inactive", "failed", "unknown"):
            raise ValueError("Stop the new radio target before installing/upgrading")
    current = INSTALL / "current"
    for unit in UNITS:
        if (Path("/etc/systemd/system") / unit).exists() and not current.exists():
            raise ValueError("An existing aoc unit has no installed release ownership record")
    entry = Path("/usr/local/bin/aocctl")
    if entry.exists() and (not entry.is_symlink() or os.readlink(entry) != str(current / "scripts/aocctl")):
        raise ValueError("The CLI entrypoint is already owned by another installation")
    for folder in (INSTALL, INSTALL / "releases", CONFIG, Path("/var/lib/agentic-ocudu"), Path("/var/log/agentic-ocudu")):
        if folder.is_symlink():
            raise ValueError("Installation directory must not be a symlink")
        folder.mkdir(parents=True, exist_ok=True)
        os.chown(folder, 0, 0)
        folder.chmod(0o755 if folder == INSTALL or folder == INSTALL / "releases" else 0o700)
    release = INSTALL / "releases" / manifest["release_id"]
    if not release.exists():
        shutil.copytree(stage / "release", release)
    for path in release.rglob("*"):
        if path.is_symlink():
            raise ValueError("Installed release must not contain symlinks")
        os.chown(path, 0, 0)
        path.chmod(0o755 if path.is_dir() or path.parent.name == "bin" or path.name == "aocctl" else 0o644)
    os.chown(release, 0, 0)
    release.chmod(0o755)
    for relative, expected in manifest["files"].items():
        if digest(release / relative) != expected:
            raise ValueError("Installed code checksum mismatch")
    for name in ("spark.json", "radio.json"):
        destination = CONFIG / name
        if not destination.exists():
            write_json(destination, json.loads((stage / name).read_text()))
        elif name == "spark.json" and json.loads(destination.read_text()) != json.loads((stage / name).read_text()):
            raise ValueError("Existing environment differs; configuration migration requires review")
    if not (CONFIG / "core").exists():
        shutil.copytree(stage / "core", CONFIG / "core")
        for path in (CONFIG / "core").rglob("*"):
            os.chown(path, 0, 0)
            path.chmod(0o700 if path.is_dir() else (0o644 if path.name in ("schema.sql", "ext-dn.sh") else 0o600))
        (CONFIG / "core").chmod(0o700)
    units = {}
    verify_dir = stage / "rendered-units"
    verify_dir.mkdir(exist_ok=True)
    for name in UNITS:
        template = (release / "deploy/spark/stack/systemd" / (name + ".in")).read_text()
        rendered = template.replace("@RELEASE@", str(release)).replace("@CONFIG@", str(CONFIG))
        if "@" in rendered:
            raise ValueError("Unresolved service template substitution")
        (verify_dir / name).write_text(rendered)
        units[name] = hashlib.sha256(rendered.encode()).hexdigest()
    subprocess.run(["systemd-analyze", "verify", *[str(verify_dir / name) for name in UNITS]], check=True)
    manifest["units"] = units
    manifest["legacy_launcher_sha256"] = LAUNCHER_SHA
    write_json(release / "release.json", manifest)
    (release / "release.json").chmod(0o644)
    for name in UNITS:
        target = Path("/etc/systemd/system") / name
        shutil.copyfile(verify_dir / name, target)
        target.chmod(0o644)
    pending = INSTALL / ".current-next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(release)
    os.replace(pending, current)
    if not entry.exists():
        entry.symlink_to(current / "scripts/aocctl")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    # Recreate only the new core to move its mounts into root-owned configuration.
    argv = ["docker", "compose", "--project-name", "aoc-cn5g", "--project-directory", str(CONFIG / "core"),
            "-f", str(CONFIG / "core/compose.json")]
    try:
        subprocess.run(argv + ["up", "-d", "--force-recreate", "--wait", "--wait-timeout", "240"], check=True, timeout=300)
        subprocess.run(["/usr/bin/python3", "-I", str(release / "scripts/radio_runtime.py"), "core-check"], check=True)
    except BaseException:
        subprocess.run(argv + ["stop", "--timeout", "30"], check=False, timeout=90)
        raise
    print("Installed release " + manifest["release_id"] + "; core/IMS ready; no RF started and no services enabled at boot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print("Staged release verified: " + verify_stage(args.stage.resolve())["release_id"])
    else:
        install(args.stage.resolve())
