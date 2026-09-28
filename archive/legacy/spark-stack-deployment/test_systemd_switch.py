#!/usr/bin/env python3
"""Exercise the production dependency graph using user services and a fake RF lock."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def fixture(directory, kind):
    def event(value):
        with (directory / "events.jsonl").open("a") as output:
            output.write(json.dumps({"time": time.time(), "kind": kind, "event": value}) + "\n")

    if (directory / (kind + "-fail")).exists():
        event("startup-failure")
        return 1
    with (directory / "fake-rf.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            event("OVERLAP")
            return 2
        event("acquired")

        def stop(signum, frame):
            if (directory / (kind + "-hang")).exists():
                event("ignoring-stop")
                return
            event("released")
            sys.exit(0)

        signal.signal(signal.SIGTERM, stop)
        while True:
            signal.pause()


def run_tests(directory):
    if os.geteuid() == 0 or not sys.platform.startswith("linux"):
        raise ValueError("Run unprivileged on Linux with a user systemd manager")
    directory = directory.resolve()
    if directory.exists():
        raise ValueError("Use a fresh output directory")
    directory.mkdir(parents=True, mode=0o700)
    prefix = "aoc-test-" + uuid.uuid4().hex[:12]
    names = {"old": prefix + "-old.service", "gnb": prefix + "-gnb.service",
             "core": prefix + "-core.service", "target": prefix + ".target"}
    unit_dir = Path.home() / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    if any(c in str(directory) + str(script) for c in ' \t\n%"'):
        raise ValueError("Test paths must not contain systemd quoting characters")
    fake = "/usr/bin/python3 {} --fixture --output {} --kind ".format(script, directory)
    created = []

    def ctl(*args, check=True):
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                              timeout=20, check=check)

    def active(name):
        return ctl("is-active", names[name], check=False).stdout.strip() == "active"

    def clear():
        ctl("stop", *names.values(), check=False)
        ctl("reset-failed", *names.values(), check=False)

    def verify_old():
        assert active("old") and not any(active(k) for k in ("gnb", "core", "target"))

    completed = []
    try:
        for key in ("gnb", "core", "target"):
            template = ROOT / "deploy/spark/stack/systemd" / ("aoc-stack.target.in" if key == "target" else "aoc-" + key + ".service.in")
            lines = []
            for line in template.read_text().splitlines():
                if line.startswith(("Requires=docker", "After=docker", "Wants=network", "Limit")):
                    continue
                if line.startswith("ExecStartPre="):
                    line = "ExecStartPre=/bin/true"
                elif line.startswith("ExecStartPost="):
                    line = "ExecStartPost=/bin/sleep 0.2"
                elif line.startswith("ExecStart="):
                    line = "ExecStart=" + (fake + "new" if key == "gnb" else "/bin/true")
                elif line.startswith("ExecStop="):
                    line = "ExecStop=/bin/true"
                elif line.startswith("TimeoutStopSec="):
                    line = "TimeoutStopSec=2"
                for original, replacement in {"oai-gnb.service": names["old"], "aoc-gnb.service": names["gnb"],
                                               "aoc-core.service": names["core"], "aoc-stack.target": names["target"]}.items():
                    line = line.replace(original, replacement)
                lines.append(line)
            path = unit_dir / names[key]
            path.write_text("\n".join(lines) + "\n")
            created.append(path)
        old = unit_dir / names["old"]
        old.write_text("[Unit]\nDescription=Agentic test old radio\n[Service]\nType=exec\nExecStart=" + fake +
                       "old\nExecStartPost=/bin/sleep 0.2\nTimeoutStopSec=2\nKillMode=control-group\n")
        created.append(old)
        ctl("daemon-reload")
        for _ in range(5):
            ctl("reset-failed", *names.values(), check=False)
            ctl("start", names["old"])
            verify_old()
            ctl("start", names["target"])
            assert all(active(k) for k in ("target", "gnb", "core")) and not active("old")
            ctl("start", names["old"])
            verify_old()
        completed.append("five_round_trips_and_child_stop_propagation")

        (directory / "new-fail").touch()
        result = ctl("start", names["target"], check=False)
        assert result.returncode != 0
        clear()
        (directory / "new-fail").unlink()
        ctl("start", names["old"])
        verify_old()
        completed.append("new_radio_start_failure_and_explicit_recovery")

        ctl("start", names["target"])
        (directory / "new-hang").touch()
        ctl("start", names["old"])
        verify_old()
        status = ctl("show", names["gnb"], "-p", "Result", "--value").stdout.strip()
        assert status == "timeout", status
        (directory / "new-hang").unlink()
        completed.append("stop_timeout_kills_fake_owner_before_old_start")
        clear()

        for _ in range(5):
            processes = [subprocess.Popen(["systemctl", "--user", "start", names[k]],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                         for k in ("old", "target")]
            for process in processes:
                process.wait(timeout=20)
            assert not (active("old") and active("gnb"))
            clear()
        completed.append("five_concurrent_start_races")
        assert "OVERLAP" not in (directory / "events.jsonl").read_text()
        report = {"passed": completed, "rf_opened": False, "scope": "user-systemd substitutes",
                  "production_installation_verified": False}
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        clear()
        for path in created:
            path.unlink(missing_ok=True)
        ctl("daemon-reload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--kind", choices=("old", "new"))
    args = parser.parse_args()
    if args.fixture:
        sys.exit(fixture(args.output, args.kind))
    run_tests(args.output)
