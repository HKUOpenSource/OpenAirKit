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


PLATFORM = "jetson"
PORT = 8878
UNITS = ("aoc-v2-jetson-device.service", "aoc-v2-jetson-web.service")
TOOLS = ("sudo", "systemctl", "ss")
ACTIONS = frozenset({"status", "start", "stop", "ue-status"})
DEVICE_SOCKET = Path("/run/aoc-v2-jetson/device.sock")


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


def device_socket_state():
    try:
        return "present" if DEVICE_SOCKET.exists() else "absent"
    except PermissionError:
        # The running executor's 0750 runtime directory is intentionally private.
        output = run(["ss", "-H", "-x", "-a"])
        if any(str(DEVICE_SOCKET) in line.split() for line in output.splitlines()):
            return "present (kernel)"
        return "inaccessible"


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

    def ready(self):
        value = units()
        if not all(running(v) for v in value.values()):
            return False
        result = health()
        return result.get("status") == "ok" and result.get("web") == "ok"

    def start(self):
        value = self.stable()
        if not all(running(v) for v in value.values()):
            if any(v["ActiveState"] == "active" and not running(v) for v in value.values()):
                raise RuntimeError("An active service is unhealthy; no restart will be attempted")
        # The manager also prepares owned routes and resumes observation when
        # services are already running in maintenance mode.
        maintain("start")
        wait_for(self.ready, "Jetson services and web health")
        # A working RPC is required; disconnected UE evidence is informational.
        state = maintain("ue-status")
        if state.get("maintenance") is not False or state.get("recovery_paused") is not True:
            raise RuntimeError("Services started, but observation was not resumed with recovery paused")
        print("Services and data routes ready; observation enabled, automatic recovery paused. "
              "UE connectivity is reported separately.", flush=True)

    def stop(self):
        value = self.stable()
        # Always retry journal-aware cleanup, including after a partial stop.
        maintain("stop")
        wait_for(lambda: all(stopped(v) for v in units().values())
                 and device_socket_state() == "absent" and not listening(), "Jetson shutdown")

    def details(self, value):
        state = "ready" if all(running(v) for v in value.values()) else (
            "stopped" if all(stopped(v) for v in value.values()) else "partial")
        print("Services: " + state, flush=True)
        if running(value[UNITS[1]]):
            print("Web health: " + json.dumps(health()), flush=True)
        if running(value[UNITS[0]]):
            state = maintain("ue-status")
            # Deliberately omit free-form modem/network details and identifiers.
            fields = ("quality", "health", "connected", "registered", "data_session_active",
                      "lab_policy_match", "management_protected", "maintenance", "recovery_paused")
            print("UE state: " + json.dumps({k: state.get(k) for k in fields}), flush=True)
            observation = ("paused" if state.get("maintenance") else
                           "current" if state.get("quality") == "ok" else "unavailable")
            connectivity = ("verified" if state.get("quality") == "ok" and state.get("connected")
                            and not state.get("maintenance") else "not verified")
            print("Observation: " + observation + "; connectivity: " + connectivity, flush=True)
            if state.get("quality") != "ok" or not state.get("connected"):
                print("WARNING: UE connection is not currently verified; no recovery was requested.", flush=True)
        print("Web listener: " + ("present (ownership not inferred)" if listening() else "absent"), flush=True)
        print("Device socket: " + device_socket_state(), flush=True)


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
