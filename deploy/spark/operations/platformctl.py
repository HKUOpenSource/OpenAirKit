#!/usr/bin/python3
"""Standalone, unprivileged lifecycle entrypoint; privileged actions use aoc-maintain."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

HELPER = "/usr/local/sbin/aoc-maintain"
COMMAND_TIMEOUT = 330
HEALTH_TIMEOUT = 60
WAIT_DEADLINE = None
ENV = {**os.environ, "PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}


PLATFORM = "spark"
PORT = 8877
CORE = "aoc-v2-core.service"
RADIO = "aoc-v2-radio.service"
MONITOR = ("aoc-control.service", "aoc-observe.service", "aoc-monitor-web.service")
UNITS = (CORE, RADIO, *MONITOR)
TOOLS = ("sudo", "systemctl", "ss", "docker")
ACTIONS = frozenset({"status", "start", "stop", "core-start", "core-stop", "radio-start", "radio-stop"})
DOCKER = ("docker", "--host", "unix:///var/run/docker.sock")
PROJECT = "aoc-v2-open5gs"
SERVICES = frozenset({"mongo", "nrf", "amf", "smf", "upf", "udr", "udm", "ausf",
                      "pcf", "nssf", "bsf", "ext-dn"})
N2_ENDPOINT = "http://172.28.81.12:9090/gnb-info?page=-1"


def n2_ready():
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with http.open(N2_ENDPOINT, timeout=remaining(3)) as response:
            payload = json.loads(response.read(1024 * 1024))
        rows = payload.get('items', [])
        return len(rows) == 1 and rows[0].get('ng', {}).get('setup_success') is True
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def containers():
    identifiers = run([*DOCKER, "ps", "-aq", "--filter", "label=com.docker.compose.project=" + PROJECT]).split()
    if not identifiers:
        return []
    # Project-scoped IDs only; never retrieve environments, mounts or credentials.
    template = ('{{index .Config.Labels "com.docker.compose.project"}}|'
                '{{index .Config.Labels "com.docker.compose.service"}}|'
                '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')
    lines = run([*DOCKER, "inspect", "--format", template, *identifiers]).splitlines()
    result = []
    for line in lines:
        project, service, state, quality = line.split("|")
        if project != PROJECT or service not in SERVICES:
            raise RuntimeError("Unexpected container ownership; manual inspection required")
        result.append({"service": service, "state": state, "health": quality})
    if len(lines) != len(identifiers):
        raise RuntimeError("Incomplete container inspection")
    return result


def core_healthy(values):
    return (len(values) == len(SERVICES) and {v["service"] for v in values} == SERVICES
            and all(v["state"] == "running" and v["health"] == "healthy" for v in values))


def core_stopped(values):
    return all(v["state"] in ("exited", "created", "dead") for v in values)


def core_active(value):
    return value.get("ActiveState") == "active" and value.get("SubState") == "exited"


class BusyError(RuntimeError):
    pass


@contextmanager
def operation_lock():
    directory = Path.home() / ".local/state/aoc-ops"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(directory / (PLATFORM + ".lock"),
                         os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BusyError("Another lifecycle script is running") from None
        yield


def remaining(timeout):
    if WAIT_DEADLINE is None:
        return timeout
    left = WAIT_DEADLINE - time.monotonic()
    if left <= 0:
        raise TimeoutError("Health deadline reached")
    return min(timeout, left)


def run(argv, timeout=20):
    result = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            env=ENV, timeout=remaining(timeout))
    if result.returncode:
        detail = (result.stderr.strip() or result.stdout.strip())[-1200:]
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {detail}")
    return result.stdout


def maintain(action):
    if action not in ACTIONS:
        raise ValueError("Unsupported maintenance action")
    print(f"Maintenance: {action}", flush=True)
    value = json.loads(run(["sudo", "-n", HELPER, action], COMMAND_TIMEOUT))
    if not isinstance(value, dict) or value.get("ok") is False:
        raise RuntimeError("Maintenance returned an invalid response")
    return value


def units():
    properties = ("Id", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID")
    output = run(["systemctl", "show", *UNITS, "--no-pager",
                  *["--property=" + key for key in properties]])
    result = {}
    for block in output.strip().split("\n\n"):
        item = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        name = item.get("Id")
        if name:
            result[name] = item
    if (set(result) != set(UNITS) or any(
            v.get("LoadState") != "loaded" or not set(properties).issubset(v)
            or not v.get("MainPID", "").isdigit() or not v.get("ControlPID", "").isdigit()
            for v in result.values())):
        raise RuntimeError("Required platform units are missing or unavailable")
    return result


def running(value):
    return (value.get("ActiveState") == "active" and value.get("SubState") == "running"
            and int(value.get("MainPID", 0)) > 0)


def stopped(value):
    return (value.get("ActiveState") in ("inactive", "failed")
            and int(value.get("MainPID", -1)) == 0 and int(value.get("ControlPID", -1)) == 0)


def health():
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with http.open(f"http://127.0.0.1:{PORT}/api/v1/health", timeout=remaining(3)) as response:
        value = json.loads(response.read(65536))
    if not isinstance(value, dict):
        raise ValueError("Invalid health response")
    return value


def listening():
    return bool(run(["ss", "-H", "-ltn", f"sport = :{PORT}"]).strip())


def wait_for(check, description):
    global WAIT_DEADLINE
    previous = WAIT_DEADLINE
    WAIT_DEADLINE = time.monotonic() + HEALTH_TIMEOUT
    detail = "condition not met"
    try:
        while True:
            try:
                if check():
                    return
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                detail = str(error)
            left = WAIT_DEADLINE - time.monotonic()
            if left <= 0:
                raise RuntimeError(f"Timed out waiting for {description}: {detail}")
            time.sleep(min(1, left))
    finally:
        WAIT_DEADLINE = previous


class Controller:
    def preflight(self):
        for executable in TOOLS:
            if not shutil.which(executable, path=ENV["PATH"]):
                raise RuntimeError("Required command missing: " + executable)
        if not os.access(HELPER, os.X_OK):
            raise RuntimeError("Restricted maintenance helper is not installed")
        units()
        if maintain("status").get("platform") != PLATFORM:
            raise RuntimeError("Maintenance helper belongs to another platform")

    def stable(self):
        value = units()
        if any(v["ActiveState"] not in ("active", "inactive", "failed")
               or int(v["ControlPID"]) != 0 for v in value.values()):
            raise RuntimeError("A service operation is in progress; inspect status before retrying")
        return value

    def report(self):
        value = units()
        print(json.dumps({"platform": PLATFORM, "services": value}, indent=2), flush=True)
        self.details(value)

    def failure_report(self):
        try:
            self.report()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print("Status incomplete: " + str(error), file=sys.stderr)

    def monitor_ready(self):
        value = units()
        if not all(running(value[name]) for name in MONITOR):
            return False
        result = health()
        return result.get("status") == "ok" and result.get("collector") == "ok"

    def start(self):
        value = self.stable()
        existing = containers()
        if core_active(value[CORE]):
            if not core_healthy(existing):
                raise RuntimeError("Active core is unhealthy; no restart will be attempted")
        else:
            if value[CORE]["ActiveState"] == "active":
                raise RuntimeError("Unexpected core service state")
            if not core_stopped(existing) and not core_healthy(existing):
                raise RuntimeError("Core containers are partially running or unhealthy; inspect before retrying")
            maintain("core-start")
        wait_for(lambda: core_active(units()[CORE]) and core_healthy(containers()), "Open5GS health")
        value = units()
        if not running(value[RADIO]):
            if value[RADIO]["ActiveState"] == "active":
                raise RuntimeError("Active radio is unhealthy; no restart will be attempted")
            maintain("radio-start")
        wait_for(lambda: running(units()[RADIO]), "gNB startup checks")
        wait_for(n2_ready, "N2 NG Setup")
        value = units()
        if not all(running(value[name]) for name in MONITOR):
            if any(value[name]["ActiveState"] == "active" and not running(value[name]) for name in MONITOR):
                raise RuntimeError("An active monitor service is unhealthy; no restart will be attempted")
            maintain("start")
        wait_for(self.monitor_ready, "Spark monitoring health")
        if not core_active(units()[CORE]) or not running(units()[RADIO]) or not core_healthy(containers()):
            raise RuntimeError("Stack changed during startup; inspect status")
        print("Stack and monitor ready. UE attachment is not certified by service health.", flush=True)

    def stop(self):
        value = self.stable()
        if not stopped(value[RADIO]):
            maintain("radio-stop")
        wait_for(lambda: stopped(units()[RADIO]), "gNB shutdown")
        value = units()
        if not stopped(value[CORE]):
            maintain("core-stop")
        wait_for(lambda: stopped(units()[CORE]) and core_stopped(containers()), "Open5GS shutdown")
        value = units()
        if not all(stopped(value[name]) for name in MONITOR):
            maintain("stop")
        wait_for(lambda: all(stopped(value) for name, value in units().items() if name in MONITOR) and not listening(),
                 "Spark monitoring shutdown")
        if not stopped(units()[RADIO]) or not stopped(units()[CORE]) or not core_stopped(containers()):
            raise RuntimeError("Stack changed during shutdown; inspect status")

    def details(self, value):
        core = containers()
        print("Core containers: " + json.dumps(core), flush=True)
        print("Stack readiness: " + json.dumps({
            "core": "ready" if core_active(value[CORE]) and core_healthy(core) else "not_ready",
            "radio": "running" if running(value[RADIO]) else "stopped",
            "n2": "ready" if core_active(value[CORE]) and running(value[RADIO]) and n2_ready() else "not_verified",
            "ue_connectivity": "requires_device_evidence"}), flush=True)
        if running(value[MONITOR[-1]]):
            print("Web health: " + json.dumps(health()), flush=True)
        print("Web listener: " + ("present" if listening() else "absent"), flush=True)


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=PLATFORM.title() + " platform lifecycle")
    parser.add_argument("action", choices=("start", "stop", "status"))
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, interrupted)
    controller = Controller()
    try:
        with operation_lock():
            try:
                controller.preflight()
                if args.action == "status":
                    controller.report()
                else:
                    getattr(controller, args.action)()
                    controller.report()
                    print(f"{PLATFORM.title()} {args.action} completed.", flush=True)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
                print("ERROR: " + (str(error) or "Operation interrupted"), file=sys.stderr)
                print("State preserved. Query status before retrying; an underlying systemd job "
                      "may still be running. No automatic rollback or retry was requested.", file=sys.stderr)
                controller.failure_report()
                return 1
    except BusyError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 3
    except OSError as error:
        print("ERROR: Cannot acquire operation lock: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
