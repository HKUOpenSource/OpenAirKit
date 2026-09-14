"""Offline V2 install, explicit serial takeover, bounded stop and rollback."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time


BASE = Path("/opt/agentic-ocudu/jetson")
ETC = Path("/etc/aoc-v2-jetson")
STATE = Path("/var/lib/aoc-v2-jetson")
WEB_STATE = Path("/var/lib/aoc-v2-jetson-web")
UNITS = ("aoc-v2-jetson-device.service", "aoc-v2-jetson-web.service")
OLD_CONTROLLERS = ("oai-console.service", "aoc-jetson-agent.service")


def run(argv, timeout=30, check=True):
    return subprocess.run(argv, check=check, timeout=timeout, text=True,
                          capture_output=True)


def output(argv, timeout=30):
    return run(argv, timeout).stdout.strip()


def unit_state(unit):
    result = run(["systemctl", "show", unit, "-p", "ActiveState", "--value"], check=False)
    return result.stdout.strip() if result.returncode == 0 else "not-found"


def verify(stage):
    stage = stage.resolve()
    manifest = json.loads((stage / "manifest.json").read_text())
    expected = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True).encode()).hexdigest()[:16]
    if manifest.get("product") != "agentic-ocudu-jetson" or not re.fullmatch(r"[a-f0-9]{16}", manifest.get("release", "")) \
            or manifest["release"] != expected:
        raise ValueError("Invalid content-addressed V2 release")
    for name, digest in manifest["files"].items():
        path = stage / name
        if path.is_symlink() or not path.resolve().is_relative_to(stage):
            raise ValueError("Unsafe package path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Checksum mismatch: " + name)
    actual = {str(path.relative_to(stage)) for path in stage.rglob("*")
              if path.is_file() and path.name != "manifest.json"}
    if actual != set(manifest["files"]):
        raise ValueError("Unexpected package contents")
    legacy = [name for name in actual if "aoc_jetson_v1" in name or "retired-integration" in name.lower()]
    if legacy:
        raise ValueError("Historical Jetson integration entered the V2 release")
    return manifest


def preflight(check_listener=True):
    if platform.machine() != "aarch64" or sys.version_info[:2] != (3, 10):
        raise ValueError("This release requires ARM64 Python 3.10")
    for name in ("ip", "nmcli", "iperf3", "systemctl", "fuser"):
        if not shutil.which(name):
            raise ValueError("Missing required command: " + name)
    if not Path("/sys/class/net/tailscale0").exists():
        raise ValueError("The commissioned Tailscale management interface is unavailable")
    wifi = [path.name for path in Path("/sys/class/net").iterdir() if (path / "wireless").exists()]
    if len(wifi) != 1:
        raise ValueError("A unique management Wi-Fi interface was not found")
    if check_listener:
        with socket.socket() as listener:
            # Match the Web server's reusable listener semantics so recently
            # closed SSE/TCP connections do not look like a live port owner.
            # A process that is still listening continues to make bind fail.
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 8878))
    return {"passed": True, "architecture": "aarch64", "python": "3.10",
            "wifi": wifi[0], "tailscale": "tailscale0", "listener": "available" if check_listener else "not-tested"}


def private_write(path, value, uid=0, gid=0, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + str(time.time_ns()))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(descriptor, "w") as output_file:
            json.dump(value, output_file, indent=2)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.chown(temporary, uid, gid)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def database_backup(source, destination):
    with sqlite3.connect(source) as current, sqlite3.connect(destination) as saved:
        current.backup(saved)


def backup():
    target = BASE / "backups" / str(time.time_ns())
    target.mkdir(parents=True)
    if (BASE / "current").exists():
        (target / "release").write_text(str((BASE / "current").resolve()))
    for name, source in (("device.db", STATE / "device.db"), ("auth.db", WEB_STATE / "auth.db")):
        if source.exists():
            database_backup(source, target / name)
    if ETC.exists():
        shutil.copytree(ETC, target / "config")
    target.chmod(0o700)
    return target


def install(stage):
    manifest = verify(stage)
    if any(unit_state(unit) == "active" for unit in UNITS):
        raise ValueError("Stop the V2 Jetson platform before upgrading")
    inventory = preflight(True)
    release = BASE / "releases" / manifest["release"]
    if release.exists():
        raise ValueError("Release already exists; use start or select a rollback")
    password_hash = None
    if not (ETC / "web.json").exists():
        password = getpass.getpass("New Jetson V2 console password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if len(password) < 12 or password != confirmation:
            raise ValueError("Password confirmation failed; no installation changes made")
        salt = os.urandom(16).hex()
        password_hash = salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    backup_record = backup()
    shutil.copytree(stage, release)
    verify(release)
    for path in (release, *release.rglob("*")):
        os.chown(path, 0, 0)
        path.chmod(0o755 if path.is_dir() else 0o644)
    try:
        output([sys.executable, "-m", "venv", str(release / "venv")])
        output([str(release / "venv/bin/python"), "-m", "pip", "install", "--no-index",
                "--find-links", str(release / "wheels"), "-r", str(release / "requirements.lock")], 180)
        output([str(release / "venv/bin/python"), "-I", "-c", "import fastapi,serial,uvicorn"])
    except Exception:
        shutil.rmtree(release)
        raise
    try:
        user = pwd.getpwnam("aoc-v2-jetson-web")
    except KeyError:
        output(["useradd", "--system", "--user-group", "--no-create-home",
                "--shell", "/usr/sbin/nologin", "aoc-v2-jetson-web"])
        user = pwd.getpwnam("aoc-v2-jetson-web")
    for directory, uid, gid, mode in ((STATE, 0, 0, 0o700),
                                      (WEB_STATE, user.pw_uid, user.pw_gid, 0o700),
                                      (ETC, 0, user.pw_gid, 0o750)):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(mode)
        os.chown(directory, uid, gid)
    Path("/var/lib/agentic-ocudu/v2-ue").mkdir(mode=0o700, parents=True, exist_ok=True)
    device = json.loads((ETC / "device.json").read_text()) if (ETC / "device.json").exists() \
        else json.loads((stage / "device.example.json").read_text())
    device["release"] = manifest["release"]
    sys.path.insert(0, str(release / "backend"))
    from aoc_jetson.config import validate
    device = validate(device)
    private_write(ETC / "device.json", device)
    web = json.loads((ETC / "web.json").read_text()) if (ETC / "web.json").exists() else {
        "web_state_dir": str(WEB_STATE), "agent_socket": "/run/aoc-v2-jetson/device.sock",
        "password_hash": password_hash, "secure_cookie": False}
    web.update(frontend_dir=str(BASE / "current/frontend"), release=manifest["release"])
    private_write(ETC / "web.json", web, 0, user.pw_gid, 0o640)
    link = BASE / "current.new"
    link.symlink_to(release)
    os.replace(link, BASE / "current")
    for unit in UNITS:
        shutil.copyfile(release / "deploy" / unit, Path("/etc/systemd/system") / unit)
    output(["systemctl", "daemon-reload"])
    output(["systemctl", "start", "aoc-v2-jetson-web.service"])
    print(json.dumps({"installed": manifest["release"], "backup": backup_record.name,
                      "web": "http://127.0.0.1:8878", "device_started": False,
                      "enabled_at_boot": False, "preflight": inventory}))


def stop(emit=True):
    started = time.monotonic()
    results = {}
    for unit, timeout in (("aoc-v2-jetson-device.service", 70), ("aoc-v2-jetson-web.service", 25)):
        result = run(["systemctl", "stop", unit], timeout=timeout, check=False)
        results[unit] = {"returncode": result.returncode, "state": unit_state(unit),
                         "detail": (result.stderr.strip() or result.stdout.strip())[:240]}
    if any(value["state"] not in {"inactive", "failed", "not-found"} for value in results.values()):
        raise ValueError("V2 platform did not stop within its bounded service timeout")
    socket_path = Path("/run/aoc-v2-jetson/device.sock")
    if socket_path.exists():
        raise ValueError("Device socket remains after stop")
    result = {"stopped": True, "seconds": round(time.monotonic() - started, 3), "results": results}
    if emit:
        print(json.dumps(result))
    return result


def start():
    sys.path.insert(0, str(BASE / "current/backend"))
    from aoc_jetson.config import load
    config = load(ETC / "device.json")
    if not config.get("commissioned") or not config.get("management_verified"):
        raise ValueError("Run explicit takeover before starting the device executor")
    output(["systemctl", "start", "aoc-v2-jetson-web.service", "aoc-v2-jetson-device.service"], 70)
    print(json.dumps({"started": True, "services": {unit: unit_state(unit) for unit in UNITS}}))


def takeover(confirmed):
    if not confirmed:
        raise ValueError("Confirm the previous console is in maintenance before takeover")
    for unit in OLD_CONTROLLERS:
        run(["systemctl", "stop", unit], timeout=70, check=False)
    deadline = time.monotonic() + 70
    while any(unit_state(unit) not in {"inactive", "failed", "not-found"} for unit in OLD_CONTROLLERS):
        if time.monotonic() >= deadline:
            raise ValueError("A previous device controller did not stop within 70 seconds")
        time.sleep(1)
    for port in Path("/dev").glob("ttyUSB*"):
        owner = run(["fuser", str(port)], timeout=5, check=False)
        if owner.returncode != 1:
            raise ValueError("Serial ownership could not be confirmed free: " + port.name)
    sys.path.insert(0, str(BASE / "current/backend"))
    from aoc_jetson.config import load, validate
    from aoc_jetson.modem import Modem
    from aoc_jetson.network import inspect
    config = load(ETC / "device.json")
    management = inspect(config)
    modem = Modem(config)
    try:
        fingerprint, _identity = modem.fingerprint()
    finally:
        modem.close()
    if config.get("sim_sha256") and config["sim_sha256"] != fingerprint:
        raise ValueError("SIM differs from the commissioned identity")
    config.update(sim_sha256=fingerprint, commissioned=True, management_verified=True)
    config = validate(config)
    private_write(ETC / "device.json", config)
    output(["systemctl", "start", "aoc-v2-jetson-device.service"], 70)
    print(json.dumps({"takeover": True, "device": unit_state(UNITS[0]),
                      "management": {"wifi_interface": management["wifi_interface"],
                                     "tailscale_interface": management["tailscale_interface"]},
                      "maintenance": True}))


def status():
    print(json.dumps({"release": str((BASE / "current").resolve()) if (BASE / "current").exists() else None,
                      "services": {unit: unit_state(unit) for unit in UNITS},
                      "previous_controllers": {unit: unit_state(unit) for unit in OLD_CONTROLLERS},
                      "enabled_at_boot": {unit: run(["systemctl", "is-enabled", unit], check=False).stdout.strip()
                                          for unit in UNITS}}))


def rollback(identifier):
    if not identifier or not identifier.isdigit():
        raise ValueError("Specify the numeric backup directory")
    record = BASE / "backups" / identifier
    release = Path((record / "release").read_text())
    if release.parent != BASE / "releases" or not release.is_dir():
        raise ValueError("Invalid rollback release")
    stop(emit=False)
    for name, directory in (("device.db", STATE), ("auth.db", WEB_STATE)):
        if (record / name).exists():
            for suffix in ("-wal", "-shm"):
                (directory / (name + suffix)).unlink(missing_ok=True)
            shutil.copyfile(record / name, directory / name)
    if (record / "config").exists():
        shutil.copytree(record / "config", ETC, dirs_exist_ok=True)
    user = pwd.getpwnam("aoc-v2-jetson-web")
    if (WEB_STATE / "auth.db").exists():
        os.chown(WEB_STATE / "auth.db", user.pw_uid, user.pw_gid)
    link = BASE / "current.new"
    link.symlink_to(release)
    os.replace(link, BASE / "current")
    output(["systemctl", "start", "aoc-v2-jetson-web.service"])
    print(json.dumps({"rolled_back": True, "release": release.name,
                      "device_started": False, "inspection_required": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("verify", "preflight", "install", "takeover", "start", "stop", "status", "rollback"))
    parser.add_argument("--stage", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--previous-maintenance-confirmed", action="store_true")
    parser.add_argument("--backup")
    arguments = parser.parse_args()
    if arguments.action == "verify":
        print(json.dumps(verify(arguments.stage)))
        return
    if arguments.action == "preflight":
        print(json.dumps(preflight()))
        return
    if arguments.action == "status":
        status()
        return
    if os.geteuid() != 0:
        raise SystemExit("Run this reviewed operation with sudo in the Jetson terminal")
    if arguments.action == "install":
        install(arguments.stage)
    elif arguments.action == "takeover":
        takeover(arguments.previous_maintenance_confirmed)
    elif arguments.action == "start":
        start()
    elif arguments.action == "stop":
        stop()
    elif arguments.action == "rollback":
        rollback(arguments.backup)


if __name__ == "__main__":
    main()
