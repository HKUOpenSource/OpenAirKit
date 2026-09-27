"""Check OCUDU's modem resource without managing external services."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, "/opt/agentic-ocudu/jetson/current/backend")
from aoc_jetson.config import load
from aoc_jetson.hardware import discover


config = load("/etc/aoc-v2-jetson/device.json")
port = discover(config)["at_port"]
owner = subprocess.run(["fuser", port], capture_output=True, text=True, check=False, timeout=5)
if owner.returncode != 1:
    raise SystemExit("AT serial port is not free: " + port)
print(json.dumps({"guard": "passed", "at_port": Path(port).name, "serial": "available"}))
