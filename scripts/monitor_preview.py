#!/usr/bin/env python3
"""Local preview with real captured telemetry and switching disabled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    state = args.state.resolve() if args.state else ROOT / "local/monitor-preview"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    salt = os.urandom(16)
    password = "Spark-Local-Preview-2026"
    auth = dict(salt=salt.hex(), password_hash=hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex())
    (state / "auth.json").write_text(json.dumps(auth))
    (state / "auth.json").chmod(0o600)
    config = dict(auth_file=str(state / "auth.json"), database=str(state / "history.db"),
                  snapshot=str(state / "snapshot.json"), frontend=str(ROOT / "apps/spark-console/frontend/dist"),
                  switch_enabled=False, port=args.port)
    (state / "config.json").write_text(json.dumps(config))
    env = dict(os.environ, PYTHONPATH=str(ROOT / "apps/spark-console/backend"), PYTHONPYCACHEPREFIX=str(ROOT / "local/pycache"))
    with (state / "server.log").open("ab") as log:
        process = subprocess.Popen([str(ROOT / "local/monitor-venv/bin/python"), "-m", "aoc_spark.web", "--config", str(state / "config.json")],
                                   env=env, cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    (state / "server.pid").write_text(str(process.pid))
    print(f"Preview PID {process.pid}, http://127.0.0.1:{args.port}; switching disabled")


if __name__ == "__main__":
    main()
