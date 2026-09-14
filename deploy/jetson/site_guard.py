"""Fail closed if another Jetson controller or an unknown serial owner is active."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, "/opt/agentic-ocudu/jetson/current/backend")
from aoc_jetson.config import load
from aoc_jetson.hardware import discover


def active(unit):
    return subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False).returncode == 0


conflicts = [unit for unit in ("oai-console.service", "aoc-jetson-agent.service") if active(unit)]
if conflicts:
    raise SystemExit("Another device controller is active: " + ", ".join(conflicts))
config = load("/etc/aoc-v2-jetson/device.json")
port = discover(config)["at_port"]
owner = subprocess.run(["fuser", port], capture_output=True, text=True, check=False, timeout=5)
if owner.returncode != 1:
    raise SystemExit("AT serial port is not free: " + port)
print(json.dumps({"guard": "passed", "at_port": Path(port).name,
                  "other_controllers": "inactive"}))
