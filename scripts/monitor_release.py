#!/usr/bin/env python3
"""Build and install the V2 single-stack Spark monitor release."""
import argparse
import getpass
import hashlib
import json
import os
import platform
from pathlib import Path
import pwd
import grp
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apps/spark-platform"
INSTALL = Path("/opt/agentic-ocudu/monitor")
CONFIG = Path("/etc/aoc-monitor")
UNITS = ("aoc-control.service", "aoc-observe.service", "aoc-monitor-web.service")
RETIRED_UNITS = ("aoc-switch.service",)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != "manifest.json"}


def stage(destination):
    sys.path.insert(0, str(ROOT))
    from scripts.release_tools import source_metadata
    if destination.exists():
        raise ValueError("Stage destination must be new")
    if not (MODULE / "frontend/dist/index.html").exists():
        raise ValueError("Build the frontend first")
    destination.mkdir(parents=True)
    shutil.copytree(MODULE / "backend", destination / "backend",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "executor.py"))
    shutil.copytree(MODULE / "frontend/dist", destination / "frontend")
    (destination / "deploy").mkdir()
    for unit in UNITS:
        shutil.copyfile(ROOT / "deploy/spark/platform" / unit, destination / "deploy" / unit)
    shutil.copytree(MODULE / "contracts", destination / "contracts")
    shutil.copyfile(MODULE / "requirements-spark.lock", destination / "requirements.lock")
    shutil.copyfile(ROOT / "scripts/spark/enable_radio_json_metrics.py", destination / "radio-metrics.py")
    (destination / "RELEASE-VERSION").write_text("0.2.1\n")
    (destination / "THIRD_PARTY_NOTICES.md").write_text("Dependencies are supplied from the locked offline wheelhouse.\n")
    (destination / "THIRD_PARTY_DEPENDENCIES.json").write_text(json.dumps({"platform":"spark","lock":"requirements.lock","wheelhouse":True}, indent=2) + "\n")
    (destination / "THIRD_PARTY_LICENSES").mkdir()
    (destination / "THIRD_PARTY_LICENSES/README.txt").write_text("See the locked wheelhouse metadata for dependency licenses.\\n")
    shutil.copyfile(Path(__file__), destination / "install.py")
    manifest = files(destination)
    release_id = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    (destination / "manifest.json").write_text(json.dumps({"release_id": release_id, "files": manifest, **source_metadata("spark")}, indent=2) + "\n")
    print("Staged V2 single-stack monitor release " + release_id)


def verify(stage):
    if any(p.is_symlink() for p in stage.rglob("*")):
        raise ValueError("Package contains symlinks")
    manifest = json.loads((stage / "manifest.json").read_text())
    actual = {k: v for k, v in files(stage).items() if not k.startswith("wheels/") and k != "wheels.json"}
    if actual != manifest["files"]:
        raise ValueError("Release file checksums differ")
    expected = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()[:16]
    if manifest["release_id"] != expected:
        raise ValueError("Release ID differs")
    if (stage / "wheels").exists() or (stage / "wheels.json").exists():
        if not (stage / "wheels").is_dir() or not (stage / "wheels.json").is_file():
            raise ValueError("Incomplete offline wheelhouse")
        if files(stage / "wheels") != json.loads((stage / "wheels.json").read_text()):
            raise ValueError("Offline wheel checksums differ")
    return manifest


def download(stage):
    sys.path.insert(0, str(ROOT))
    from scripts.release_tools import download_wheels
    verify(stage)
    checksums = download_wheels(stage / "wheels", stage / "requirements.lock", "spark")
    (stage / "wheels.json").write_text(json.dumps(checksums, indent=2) + "\n")


def require_target_host():
    if platform.system() != "Linux" or platform.machine() != "aarch64" or sys.version_info[:2] != (3, 12):
        raise ValueError("Spark installation requires Linux ARM64 Python 3.12")


def check_host(stage):
    require_target_host()
    verify(stage)
    with tempfile.TemporaryDirectory(prefix="aoc-monitor-check-") as temporary:
        root = Path(temporary)
        for unit in UNITS:
            template = (stage / "deploy" / unit).read_text()
            template = template.replace("@RELEASE@/venv/bin/python", "/usr/bin/python3").replace("@RELEASE@", str(stage))
            (root / unit).write_text(template)
        call(["systemd-analyze", "verify", *[str(root / unit) for unit in UNITS]])
    if not active('aoc-monitor-web.service'):
        wait_for_loopback_port(8877)
    print("Host unit syntax and loopback port passed; no services installed or protocol-stack operation performed")


def call(argv):
    subprocess.run(argv, check=True, timeout=240)


def active(unit):
    return subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True).stdout.strip() == "active"


def loopback_port_available(port):
    try:
        with socket.socket() as listener:
            # A cleanly stopped TCP server may leave connections in TIME_WAIT.
            # SO_REUSEADDR ignores those while an actual listener still blocks bind().
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def wait_for_loopback_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    while not loopback_port_available(port):
        if time.monotonic() >= deadline:
            raise OSError("Loopback listener conflict: 127.0.0.1:" + str(port))
        time.sleep(0.25)


def stop_if_loaded(unit):
    """Stop an installed unit while treating a retired, absent unit as already stopped."""
    state = subprocess.run(["systemctl", "show", unit, "--property=LoadState", "--value"],
                           capture_output=True, text=True, timeout=10)
    load_state = state.stdout.strip()
    missing = load_state == "not-found" or "not found" in state.stderr.lower() or "could not be found" in state.stderr.lower()
    if missing:
        return False
    if state.returncode:
        raise subprocess.CalledProcessError(state.returncode, state.args, state.stdout, state.stderr)
    call(["systemctl", "stop", unit])
    return True


def verify_health(units=UNITS):
    for _ in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8877/api/v1/health', timeout=2) as response:
                result = json.load(response)
            if result == {'status': 'ok', 'collector': 'ok'} and all(active(unit) for unit in units):
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise ValueError('Monitor startup health failed')


def root_directory(path, mode=0o755, group=0):
    if path.is_symlink():
        raise ValueError("Unexpected directory symlink: " + str(path))
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, 0, group)
    path.chmod(mode)


def write_json(path, data, group=0, mode=0o640):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output, indent=2)
    os.chown(path, 0, group)
    path.chmod(mode)


def install(stage):
    require_target_host()
    manifest = verify(stage)
    if os.geteuid() != 0:
        raise ValueError("Run install in your sudo terminal")
    if files(stage / "wheels") != json.loads((stage / "wheels.json").read_text()):
        raise ValueError("Offline wheel checksums differ")
    if not active("aoc-monitor-web.service"):
        wait_for_loopback_port(8877)
    for group in ("aoc-web", "aoc-observe", "aoc-control"):
        try:
            grp.getgrnam(group)
        except KeyError:
            call(["groupadd", "--system", group])
    try:
        account = pwd.getpwnam("aoc-web")
        if account.pw_shell not in ("/usr/sbin/nologin", "/bin/false"):
            raise ValueError("Existing aoc-web account is not a dedicated service account")
    except KeyError:
        call(["useradd", "--system", "--gid", "aoc-web", "--no-create-home", "--shell", "/usr/sbin/nologin", "aoc-web"])
    gid = grp.getgrnam("aoc-web").gr_gid
    root_directory(CONFIG, 0o750, gid)
    # A stack installed with umask 077 may have created this shared parent as
    # 0700. The unprivileged web service must traverse it to reach its release.
    # Individual stack and credential directories retain their private modes.
    root_directory(INSTALL.parent)
    root_directory(INSTALL)
    root_directory(INSTALL / "releases")
    auth_path = CONFIG / "auth.json"
    if not auth_path.exists():
        password = getpass.getpass("Set Spark monitor password (at least 12 characters): ")
        if len(password) < 12 or password != getpass.getpass("Repeat password: "):
            raise ValueError("Password length or confirmation failed")
        salt = os.urandom(16).hex()
        password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
        write_json(auth_path, {"salt": salt, "password_hash": password_hash}, gid)
        del password
    release = INSTALL / "releases" / manifest["release_id"]
    if not release.exists():
        shutil.copytree(stage, release, ignore=shutil.ignore_patterns("wheels", "wheels.json"))
        for path in release.rglob("*"):
            os.chown(path, 0, 0)
            path.chmod(0o755 if path.is_dir() else 0o644)
    for relative, expected in manifest["files"].items():
        path = release / relative
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or sha(path) != expected:
            raise ValueError("Installed release checksum or ownership differs")
    if not (release / "venv").exists():
        # The service runs as aoc-web, even when the administrator uses umask
        # 077. Only public runtime files are created in this scoped block.
        previous_umask = os.umask(0o022)
        try:
            call(["/usr/bin/python3", "-m", "venv", str(release / "venv")])
            call([str(release / "venv/bin/pip"), "install", "--no-index", "--find-links", str(stage / "wheels"), "-r", str(release / "requirements.lock")])
        finally:
            os.umask(previous_umask)
    previous = (INSTALL / "current").resolve() if (INSTALL / "current").exists() else None
    for unit in UNITS:
        target = Path("/etc/systemd/system") / unit
        if target.exists() and previous is None:
            raise ValueError("Existing monitor unit has no owned release")
    # Build units before replacing any running service.
    rendered = release / "units"
    rendered.mkdir(exist_ok=True)
    for unit in UNITS:
        (rendered / unit).write_text((release / "deploy" / unit).read_text().replace("@RELEASE@", str(release)))
    call(["systemd-analyze", "verify", *[str(rendered / unit) for unit in UNITS]])
    rollback_ready = False
    try:
        for unit in reversed(UNITS + RETIRED_UNITS):
            stop_if_loaded(unit)
        wait_for_loopback_port(8877)
        database = Path("/var/lib/aoc-web/history.db")
        database_backup = None
        if database.exists():
            root_directory(INSTALL / "backups", 0o700)
            database_backup = INSTALL / "backups" / (str(time.time_ns()) + ".db")
            with sqlite3.connect(database) as src, sqlite3.connect(database_backup) as dst:
                src.backup(dst)
        previous_config = json.loads((CONFIG / "web.json").read_text()) if (CONFIG / "web.json").exists() else None
        if previous:
            write_json(INSTALL / "previous.json", {"release": str(previous),
                       "database_backup": str(database_backup) if database_backup else None,
                       "web_config": previous_config}, mode=0o600)
            rollback_ready = True
        # Complete history-index migration before the bounded service health wait.
        if database.exists():
            call([str(release / "venv/bin/python"), "-I", "-B", "-c",
                  "import sys; sys.path.insert(0, sys.argv[1]); from aoc_spark.storage import Store; Store(sys.argv[2])",
                  str(release / "backend"), str(database)])
        config = dict(database=str(database), snapshot="/run/aoc-observe/snapshot.json", auth_file=str(auth_path),
                      frontend=str(release / "frontend"), port=8877, retention_days=7,
                      event_retention_days=30, control_socket="/run/aoc-control/control.sock",
                      secure_cookie=False)
        write_json(CONFIG / "web.json", config, gid)
        # Root collector may create only its own counters in fixed UPF namespaces.
        (CONFIG / 'traffic-enabled').touch(mode=0o600)
        for unit in UNITS:
            shutil.copyfile(rendered / unit, Path("/etc/systemd/system") / unit)
        for unit in RETIRED_UNITS:
            Path("/etc/systemd/system", unit).unlink(missing_ok=True)
        pending = INSTALL / ".current-next"
        pending.unlink(missing_ok=True)
        pending.symlink_to(release)
        os.replace(pending, INSTALL / "current")
        call(["systemctl", "daemon-reload"])
        call(["systemctl", "start", *UNITS])
        verify_health()
    except Exception as error:
        if previous:
            try:
                if rollback_ready:
                    rollback()
                else:
                    call(["systemctl", "start", *UNITS])
                    verify_health()
            except Exception as recovery_error:
                raise RuntimeError("Monitor install failed and previous release recovery failed: " + str(recovery_error)) from error
        raise
    print("V2 monitor installed at http://127.0.0.1:8877. No protocol-stack operation performed; services not enabled at boot.")


def rollback():
    if os.geteuid() != 0:
        raise ValueError("Run rollback in your sudo terminal")
    saved = json.loads((INSTALL / "previous.json").read_text())
    previous = Path(saved["release"])
    if previous.parent != INSTALL / "releases":
        raise ValueError("Invalid previous release path")
    previous_units = tuple(path.name for path in sorted((previous / "units").glob("*.service")))
    if not previous_units:
        raise ValueError("Previous release contains no service units")
    for unit in reversed(tuple(dict.fromkeys(UNITS + RETIRED_UNITS + previous_units))):
        stop_if_loaded(unit)
    database_backup = Path(saved["database_backup"]) if saved.get("database_backup") else None
    if database_backup:
        if database_backup.parent != INSTALL / "backups" or not database_backup.is_file():
            raise ValueError("Invalid database rollback backup")
        database = Path("/var/lib/aoc-web/history.db")
        with sqlite3.connect(database_backup) as source, sqlite3.connect(database) as target:
            source.backup(target)
    config = saved.get("web_config") or json.loads((CONFIG / "web.json").read_text())
    config["frontend"] = str(previous / "frontend")
    write_json(CONFIG / "web.json", config, grp.getgrnam("aoc-web").gr_gid)
    for unit in previous_units:
        shutil.copyfile(previous / "units" / unit, Path("/etc/systemd/system") / unit)
    for unit in set(UNITS + RETIRED_UNITS) - set(previous_units):
        Path("/etc/systemd/system", unit).unlink(missing_ok=True)
    pending = INSTALL / ".current-next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(previous)
    os.replace(pending, INSTALL / "current")
    call(["systemctl", "daemon-reload"])
    call(["systemctl", "start", *previous_units])
    verify_health(previous_units)


def stop_platform():
    if os.geteuid() != 0:
        raise ValueError("Run stop-platform in your sudo terminal")
    started = time.monotonic()
    for unit in reversed(UNITS):
        if active(unit):
            call(["systemctl", "stop", unit])
    states = {unit: active(unit) for unit in UNITS}
    if any(states.values()) or Path("/run/aoc-control/control.sock").exists():
        raise ValueError("Monitor services or control socket remain after stop")
    print(json.dumps({"stopped": True, "seconds": round(time.monotonic() - started, 3),
                      "services": list(UNITS), "protocol_stack_changed": False}))


def counters_disable():
    if os.geteuid() != 0:
        raise ValueError('Run counters-disable in your sudo terminal')
    running = active('aoc-observe.service')
    if running:
        call(['systemctl', 'stop', 'aoc-observe.service'])
    try:
        (CONFIG / 'traffic-enabled').unlink(missing_ok=True)
        for name in ('aoc-v2-open5gs-upf-1',):
            result = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise ValueError('Cannot inspect fixed UPF for counter cleanup: ' + name)
            container = json.loads(result.stdout)[0]
            if not container['State']['Running']:
                continue
            namespace = Path('/proc') / str(container['State']['Pid']) / 'ns/net'
            # An open descriptor pins the container namespace across process exit/PID reuse.
            with namespace.open('rb') as descriptor:
                if os.fstat(descriptor.fileno()).st_ino == Path('/proc/self/ns/net').stat().st_ino:
                    raise ValueError('Refusing counter cleanup in the host namespace')
                prefix = ['nsenter', '--net=/proc/self/fd/' + str(descriptor.fileno())]
                found = subprocess.run(prefix + ['nft', 'list', 'table', 'inet', 'aoc_spark'],
                                       capture_output=True, pass_fds=(descriptor.fileno(),), timeout=5)
                if found.returncode == 0:
                    subprocess.run(prefix + ['nft', 'delete', 'table', 'inet', 'aoc_spark'],
                                   check=True, pass_fds=(descriptor.fileno(),), timeout=5)
    finally:
        if running:
            call(['systemctl', 'start', 'aoc-observe.service'])
    print('Independent UPF counters disabled; forwarding and NAT unchanged')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "download", "verify", "check-host", "install", "rollback", "stop-platform", "counters-disable"))
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    if args.action == "rollback":
        rollback()
    elif args.action == 'stop-platform':
        stop_platform()
    elif args.action == 'counters-disable':
        counters_disable()
    elif args.path is None:
        parser.error("--path is required")
    else:
        result = globals()[args.action.replace("-", "_")](args.path.resolve())
        if args.action == "verify":
            print("Verified release " + result["release_id"])
