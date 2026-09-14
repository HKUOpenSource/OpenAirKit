#!/usr/bin/env python3
"""Root-owned, fixed-path Spark radio lifecycle. No arbitrary shell or path arguments."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.aoclib.cli import compose_args, core_healthy, core_states, inventory
from scripts.aoclib.core import write_json
from scripts.aoclib.preflight import inspect
from scripts.aoclib.radio import digest, gnb_config, validate_profile

CONFIG = Path("/etc/agentic-ocudu")
STATE = Path("/var/lib/agentic-ocudu")
LOGS = Path("/var/log/agentic-ocudu")
OPERATOR = "defaultuser"
LEGACY = "/home/defaultuser/.local/bin/oai-spark-services.sh"


class HandoffFailure(RuntimeError):
    """The new stack is confirmed stopped and the original launcher may run."""


def command(argv, **kwargs):
    return subprocess.run(argv, check=True, timeout=kwargs.pop("timeout", 60), **kwargs)


def show(unit):
    raw = subprocess.check_output(["systemctl", "show", unit, "-p", "ActiveState", "-p", "SubState",
                                   "-p", "MainPID", "-p", "ControlGroup", "-p", "Result"], text=True)
    return dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)


def record(phase, **details):
    write_json(STATE / "handoff.json", {"phase": phase, "at": datetime.now(timezone.utc).isoformat(), **details})
    print("AOC: " + phase, flush=True)


def verify_release():
    if os.geteuid() != 0:
        raise ValueError("Run through aocctl from a terminal with sudo authorization")
    if ROOT.parent != Path("/opt/agentic-ocudu/releases"):
        raise ValueError("Lifecycle commands require the installed, root-owned release")
    manifest = json.loads((ROOT / "release.json").read_text())
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or digest(path) != expected:
            raise ValueError("Installed release integrity check failed: " + relative)
    for name, expected in manifest["units"].items():
        if digest(Path("/etc/systemd/system") / name) != expected:
            raise ValueError("Installed service definition changed: " + name)
    config = json.loads((CONFIG / "spark.json").read_text())
    if digest(Path(LEGACY)) != manifest["legacy_launcher_sha256"]:
        raise ValueError("Original launcher changed; switching contract needs review")
    return config


@contextmanager
def switch_lock():
    operator = pwd.getpwnam(OPERATOR)
    runtime = Path("/run/user") / str(operator.pw_uid)
    if runtime.stat().st_uid != operator.pw_uid:
        raise ValueError("Operator runtime directory ownership mismatch")
    fd = os.open(runtime / "oai-spark-services.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as handle:
        st = os.fstat(handle.fileno())
        if st.st_uid not in (0, operator.pw_uid) or st.st_nlink != 1:
            raise ValueError("Unexpected switching lock ownership")
        os.fchown(handle.fileno(), operator.pw_uid, operator.pw_gid)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def core_command(config):
    return compose_args(config, CONFIG / "core")


def core_ready(config):
    if not core_healthy(core_states(core_command(config))):
        raise ValueError("All ten isolated core/IMS services must be healthy")


def handoff_check(config):
    validate_profile(json.loads((CONFIG / "radio.json").read_text()), serial_required=False)
    errors = inspect(config, inventory(), scope="radio")
    if errors:
        raise ValueError("; ".join(errors))
    core_ready(config)
    if not json.loads((CONFIG / "core/bundle.json").read_text()).get("subscribers_provisioned"):
        raise ValueError("No explicitly imported SIM subscription is recorded")
    print("Core, subscription marker and resources ready; B210 and UE acceptance are still pending.")


def usb_free():
    if show("oai-gnb.service").get("ActiveState") not in ("inactive", "failed"):
        raise ValueError("Original gNB has not stopped")
    for name in ("nr-softmodem", "gnb"):
        result = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True)
        if result.returncode != 1:
            raise ValueError("A radio process still exists or process inspection failed: " + name)
    devices = []
    for path in Path("/sys/bus/usb/devices").glob("*"):
        try:
            if (path / "idVendor").read_text().strip() == "2500" and (path / "idProduct").read_text().strip() == "0020":
                devices.append(path)
        except OSError:
            continue
    if len(devices) != 1:
        raise ValueError("Expected exactly one B210 USB device")
    device = devices[0]
    if float((device / "speed").read_text()) < 5000:
        raise ValueError("B210 is not on a SuperSpeed USB link")
    node = Path("/dev/bus/usb/{:03d}/{:03d}".format(int((device / "busnum").read_text()), int((device / "devnum").read_text())))
    result = subprocess.run(["fuser", str(node)], capture_output=True, text=True)
    if result.returncode != 1 or result.stdout.strip() or result.stderr.strip():
        raise ValueError("B210 is busy or USB ownership could not be established")


def discover(config):
    usb_free()
    profile = json.loads((CONFIG / "radio.json").read_text())
    validate_profile(profile, serial_required=False)
    result = command([str(ROOT / "bin/probe-b210")], capture_output=True, text=True, timeout=45)
    lines = [line.removeprefix("AOC_PROBE_JSON=") for line in result.stdout.splitlines() if line.startswith("AOC_PROBE_JSON=")]
    if len(lines) != 1:
        raise ValueError("UHD probe did not return one device record")
    probe = json.loads(lines[0])
    if profile["serial"] is not None and profile["serial"] != probe["serial"]:
        raise ValueError("B210 serial changed; refusing to select a different device")
    for direction in ("tx", "rx"):
        if not probe[direction + "_min"] <= profile[direction + "_gain"] <= probe[direction + "_max"]:
            raise ValueError("Reviewed gain is outside the probed device range")
    profile["serial"] = probe["serial"]
    write_json(CONFIG / "radio.json", profile)
    write_json(STATE / "b210-probe.json", probe)
    write_json(CONFIG / "ocudu/gnb.json", gnb_config(config, profile))
    command([str(ROOT / "bin/gnb"), "--dryrun", "-c", str(CONFIG / "ocudu/gnb.json")], timeout=30)


def preflight(config):
    profile = json.loads((CONFIG / "radio.json").read_text())
    validate_profile(profile)
    if json.loads((CONFIG / "ocudu/gnb.json").read_text()) != gnb_config(config, profile):
        raise ValueError("Installed gNB configuration differs from reviewed parameters")
    core_ready(config)
    errors = inspect(config, inventory(), scope="radio")
    if errors:
        raise ValueError("; ".join(errors))
    usb_free()
    LOGS.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = LOGS / "gnb.log"
    if log.exists():
        log.rename(LOGS / ("gnb-" + str(time.time_ns()) + ".log"))


def connection_evidence(text, pid, config):
    local, peer = config["network"]["addresses"]["gnb"], config["network"]["addresses"]["amf"]
    return any("ESTAB" in line and "pid=" + str(pid) + "," in line and
               any(re.fullmatch(re.escape(local) + r"(?:%[A-Za-z0-9_.-]+)?:[0-9]+", field) for field in line.split()) and
               peer + ":38412" in line.split() for line in text.splitlines())


def health(config, timeout=160):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = show("aoc-gnb.service")
        pid = int(state.get("MainPID", "0"))
        if state.get("ActiveState") in ("failed", "inactive"):
            raise ValueError("OCUDU exited before N2 readiness")
        if pid and Path("/proc/{}/exe".format(pid)).resolve() == ROOT / "bin/gnb":
            sctp = subprocess.check_output(["ss", "-H", "-n", "-p", "-A", "sctp"], text=True)
            log = LOGS / "gnb.log"
            recent = ""
            if log.exists():
                with log.open("rb") as handle:
                    handle.seek(max(0, log.stat().st_size - 262144))
                    recent = handle.read().decode(errors="replace")
            if connection_evidence(sctp, pid, config) and "Connected to AMF. Supported PLMNs: 46003" in recent:
                record("ran-ready", pid=pid, amf=config["network"]["addresses"]["amf"], ue_accepted=False)
                return
        time.sleep(1)
    raise TimeoutError("No matching OCUDU process, AMF association and NG Setup success within startup timeout")


def stop(config):
    command(["systemctl", "stop", "aoc-stack.target"], timeout=150)
    command(core_command(config) + ["stop", "--timeout", "30"], timeout=90)
    # This check is only applicable while the legacy radio is also stopped.
    if show("oai-gnb.service").get("ActiveState") in ("inactive", "failed"):
        usb_free()
    record("new-stack-stopped")


def restore_legacy():
    record("restoring-legacy")
    command(["runuser", "-u", OPERATOR, "--", LEGACY, "start"], timeout=360)
    if show("oai-gnb.service").get("ActiveState") != "active":
        raise ValueError("Original launcher returned without an active original gNB")
    record("legacy-restored", jetson_restore_required=True)


def start(config):
    with switch_lock():
        if show("aoc-stack.target").get("ActiveState") == "active":
            core_ready(config)
            health(config, timeout=5)
            return
        if show("oai-ext-dn-iperf3.service").get("SubState") != "running":
            raise ValueError("Original iperf supervisor is not ready for rollback")
        profile = json.loads((CONFIG / "radio.json").read_text())
        validate_profile(profile, serial_required=False)
        record("core-preflight")
        errors = inspect(config, inventory(), scope="radio")
        if errors:
            raise ValueError("; ".join(errors))
        try:
            command(core_command(config) + ["up", "-d", "--wait", "--wait-timeout", "240"], timeout=300)
            core_ready(config)
        except BaseException:
            command(core_command(config) + ["stop", "--timeout", "30"], timeout=90)
            record("core-preflight-failed-legacy-untouched")
            raise
        if not json.loads((CONFIG / "core/bundle.json").read_text()).get("subscribers_provisioned"):
            raise ValueError("No explicitly imported SIM subscription is recorded")
        record("stopping-legacy-radio")
        try:
            command(["systemctl", "stop", "oai-gnb.service"], timeout=90)
            usb_free()
            record("probing-b210")
            discover(config)
            record("starting-ocudu")
            command(["systemctl", "start", "aoc-stack.target"], timeout=200)
            core_ready(config)
            return
        except BaseException as error:
            record("handoff-failed-cleaning")
            stop(config)
            # The caller restores only after the shared launcher lock is released.
            raise HandoffFailure("Radio startup failed after legacy handoff; new stack is stopped") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "handoff-check", "health", "core-check", "core-stop", "start", "stop", "restore", "status"))
    args = parser.parse_args()
    config = verify_release()
    if args.action == "handoff-check":
        handoff_check(config)
    elif args.action == "preflight":
        preflight(config)
    elif args.action == "health":
        health(config)
    elif args.action == "core-check":
        core_ready(config)
    elif args.action == "core-stop":
        command(core_command(config) + ["stop", "--timeout", "30"], timeout=90)
    elif args.action == "status":
        print(json.dumps({"radio": show("aoc-gnb.service"), "legacy": show("oai-gnb.service"),
                          "core": core_states(core_command(config))}, indent=2))
    elif args.action == "start":
        try:
            start(config)
        except HandoffFailure:
            restore_legacy()
            raise
    else:
        with switch_lock():
            stop(config)
        if args.action == "restore":
            restore_legacy()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("AOC ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
