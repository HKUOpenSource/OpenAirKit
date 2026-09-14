"""Start the explicitly simulated, loopback-only Jetson V2 preview."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/jetson-console/backend"))
from aoc_jetson.api import password_record
from aoc_jetson.config import validate
from aoc_jetson.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8880)
    parser.add_argument("--state-dir", type=Path, default=ROOT / "local/jetson-v2-preview")
    args = parser.parse_args()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", args.port))
    root = args.state_dir.resolve()
    if not root.is_relative_to(ROOT / "local"):
        raise ValueError("Preview state must stay in the project local directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = json.loads((ROOT / "config/jetson.example.json").read_text())
    config.update(state_dir=str(root / "agent"), web_state_dir=str(root / "web"),
                  agent_socket=str(root / "device.sock"), commissioned=True,
                  management_verified=True, sim_sha256="0" * 64, simulation=True,
                  release="development-preview")
    config = validate(config)
    web = {**config, "frontend_dir": str(ROOT / "apps/jetson-console/frontend/dist"),
           "password_hash": password_record("Jetson-Local-Preview-2026")}
    for name, value in (("device", config), ("web", web)):
        path = root / (name + ".json")
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    Store(root / "agent/device.db").set("maintenance", False)
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "apps/jetson-console/backend"),
                   "PYTHONPYCACHEPREFIX": "/tmp/aoc-pycache"}
    processes = []
    for module, config_name, extra in (("agent", "device", []),
                                       ("api", "web", ["--port", str(args.port)])):
        log = (root / (module + ".log")).open("a")
        process = subprocess.Popen([sys.executable, "-m", "aoc_jetson." + module,
                                    "--config", str(root / (config_name + ".json")), *extra],
                                   env=environment, stdout=log, stderr=log, start_new_session=True)
        log.close()
        processes.append(process)
    time.sleep(2)
    if any(process.poll() is not None for process in processes):
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        raise SystemExit("Preview startup failed; inspect local/jetson-v2-preview logs")
    (root / "pids.json").write_text(json.dumps([process.pid for process in processes]))
    print("Jetson V2 simulator: http://127.0.0.1:" + str(args.port))
    print("Local preview password: Jetson-Local-Preview-2026")


if __name__ == "__main__":
    main()
