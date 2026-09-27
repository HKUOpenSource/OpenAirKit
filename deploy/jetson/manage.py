"""Offline install, independent commissioning and complete OCUDU lifecycle."""
import argparse
from contextlib import closing
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
import stat
import subprocess
import sys
import time


BASE = Path("/opt/agentic-ocudu/jetson")
ETC = Path("/etc/aoc-v2-jetson")
STATE = Path("/var/lib/aoc-v2-jetson")
WEB_STATE = Path("/var/lib/aoc-v2-jetson-web")
UNITS = ("aoc-v2-jetson-device.service", "aoc-v2-jetson-web.service")


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
    for name in ("ip", "nmcli", "systemctl", "fuser"):
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


def verify_installed(release, manifest):
    """Reuse only intact packaged code and a protected, root-owned runtime."""
    def protected(path):
        for entry in (path, *path.parents):
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("Unprotected installed release: " + str(entry))
    protected(release)
    actual = set()
    for path in release.rglob("*"):
        relative = path.relative_to(release)
        runtime = relative.parts[0] == "venv"
        if path.is_symlink():
            if not runtime or path.lstat().st_uid != 0:
                raise ValueError("Unexpected installed symlink")
            protected(path.resolve(strict=True))
            continue
        protected(path)
        if not path.is_file() and not path.is_dir():
            raise ValueError("Unexpected installed file type")
        if path.is_file() and not runtime and not (
                "__pycache__" in relative.parts and path.suffix == ".pyc"):
            actual.add(str(relative))
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Unexpected installed package contents")
    if json.loads((release / "manifest.json").read_text()) != manifest:
        raise ValueError("Installed manifest differs from the reviewed release")
    for name, expected in manifest["files"].items():
        if hashlib.sha256((release / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Installed checksum mismatch: " + name)
    if not (release / "venv/bin/python").is_file():
        raise ValueError("Installed virtual environment is missing")


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
    with closing(sqlite3.connect(source)) as current, closing(sqlite3.connect(destination)) as saved:
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
    existing = release.exists() or release.is_symlink()
    if existing:
        verify_installed(release, manifest)
    password_hash = None
    if not (ETC / "web.json").exists():
        password = getpass.getpass("New Jetson V2 console password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if len(password) < 12 or password != confirmation:
            raise ValueError("Password confirmation failed; no installation changes made")
        salt = os.urandom(16).hex()
        password_hash = salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    backup_record = backup()
    if not existing:
        shutil.copytree(stage, release)
        verify(release)
        for path in (release, *release.rglob("*")):
            os.chown(path, 0, 0)
            path.chmod(0o755 if path.is_dir() else 0o644)
    try:
        if not existing:
            output([sys.executable, "-m", "venv", str(release / "venv")])
            output([str(release / "venv/bin/python"), "-m", "pip", "install", "--no-index",
                    "--find-links", str(release / "wheels"), "-r", str(release / "requirements.lock")], 180)
        output([str(release / "venv/bin/python"), "-m", "pip", "check"])
        output([str(release / "venv/bin/python"), "-I", "-c", "import fastapi,serial,uvicorn"])
    except Exception:
        if not existing:
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
    from aoc_jetson.config import migrate, validate
    device = validate(migrate(device))
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
    if (STATE / "network-state.json").exists():
        network_action("restore")
    result = {"stopped": True, "owned_routes": "cleared",
              "seconds": round(time.monotonic() - started, 3), "results": results}
    if emit:
        print(json.dumps(result))
    return result


def network_action(action):
    return json.loads(output([str(BASE / "current/venv/bin/python"), "-I", "-B",
                              str(BASE / "current/deploy/network_entry.py"),
                              "--config", str(ETC / "device.json"), "--action", action], 50))


def device_request(request):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(55)
        client.connect('/run/aoc-v2-jetson/device.sock')
        client.sendall(json.dumps(request).encode() + b'\n')
        with client.makefile('rb') as reader:
            response = json.loads(reader.readline(1024 * 1024))
    if response.get('ok') is not True:
        raise ValueError('Device request failed: ' + str(response.get('error', 'unknown'))[:300])
    return response['result']


def wait_device():
    deadline = time.monotonic() + 15
    while True:
        try:
            return device_request({'op': 'status'})
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise ValueError('Device RPC did not become ready') from None
            time.sleep(.25)


def start():
    sys.path.insert(0, str(BASE / "current/backend"))
    from aoc_jetson.config import load
    config = load(ETC / "device.json")
    if not config.get("commissioned") or not config.get("management_verified"):
        raise ValueError("Run commission before starting the device executor")
    if unit_state(UNITS[1]) != "active":
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 8878))
    if unit_state(UNITS[0]) == "active":
        if device_request({'op': 'status'}).get('active_job'):
            raise ValueError('A device operation is active; finish or cancel it before starting')
    else:
        output([str(BASE / "current/venv/bin/python"), "-I", "-B",
                str(BASE / "current/deploy/site_guard.py")])
    routes = network_action("prepare")
    output(["systemctl", "start", "aoc-v2-jetson-web.service", "aoc-v2-jetson-device.service"], 70)
    state = wait_device()
    if state.get('maintenance') is not False or state.get('recovery_paused') is not True:
        device_request({'op': 'maintenance', 'enabled': False})
    print(json.dumps({"started": True, "observation": "enabled", "recovery_paused": True,
                      "routes": routes, "services": {unit: unit_state(unit) for unit in UNITS}}))


def commission(spark_address, wifi_interface):
    if any(unit_state(unit) == "active" for unit in UNITS):
        raise ValueError("Stop the OCUDU platform before commissioning")
    sys.path.insert(0, str(BASE / "current/backend"))
    from aoc_jetson.config import load, validate
    from aoc_jetson.hardware import discover
    from aoc_jetson.modem import Modem
    from aoc_jetson.network import inspect
    config = load(ETC / "device.json")
    config['management'].update(spark_address=spark_address, wifi_interface=wifi_interface)
    config = validate(config)
    port = discover(config)['at_port']
    owner = run(["fuser", port], timeout=5, check=False)
    if owner.returncode != 1:
        raise ValueError("Modem serial port is in use; stop its owner before commissioning")
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
    print(json.dumps({"commissioned": True, "device_started": False,
                      "management": {"wifi_interface": management["wifi_interface"],
                                     "tailscale_interface": management["tailscale_interface"]},
                      "next_action": "start"}))


def status():
    device = {"observation": "stopped", "connectivity": "not_verified"}
    if unit_state(UNITS[0]) == "active":
        try:
            value = device_request({'op': 'status'})
            device = {"observation": "paused" if value.get('maintenance') else value.get('quality', 'unknown'),
                      "connectivity": "verified" if value.get('quality') == 'ok'
                      and value.get('connected') and not value.get('maintenance') else "not_verified",
                      "recovery_paused": value.get('recovery_paused')}
        except (OSError, ValueError):
            device = {"observation": "unavailable", "connectivity": "not_verified"}
    print(json.dumps({"release": str((BASE / "current").resolve()) if (BASE / "current").exists() else None,
                      "services": {unit: unit_state(unit) for unit in UNITS},
                      "device": device,
                      "owned_route_journal": (STATE / "network-state.json").exists(),
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
    parser.add_argument("action", choices=("verify", "preflight", "install", "commission", "start", "stop", "status", "rollback"))
    parser.add_argument("--stage", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--spark-address")
    parser.add_argument("--wifi-interface", default="auto")
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
    elif arguments.action == "commission":
        if not arguments.spark_address:
            parser.error('commission requires --spark-address')
        # Commissioning imports the modem driver, never the OS Python's packages.
        runtime = BASE / 'current/venv'
        if Path(sys.prefix).resolve() != runtime.resolve():
            os.execv(str(runtime / 'bin/python'), [str(runtime / 'bin/python'), '-I', '-B',
                     str(BASE / 'current/deploy/manage.py'), *sys.argv[1:]])
        commission(arguments.spark_address, arguments.wifi_interface)
    elif arguments.action == "start":
        start()
    elif arguments.action == "stop":
        stop()
    elif arguments.action == "rollback":
        rollback(arguments.backup)


if __name__ == "__main__":
    main()
