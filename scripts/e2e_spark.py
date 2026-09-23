"""Run Spark browser checks against an isolated, synthetic loopback server."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps/spark-platform/frontend"
sys.path.insert(0, str(ROOT / "apps/spark-platform/backend"))
from aoc_spark.domain import SCHEMA_VERSION, utc
from aoc_spark.web import password_hash


def write_snapshot(path):
    value = dict(schema_version=SCHEMA_VERSION, observed_at=utc(), collector_status="ok",
                 active_stack="ocudu", observations=[], services=[], events=[], devices=[], components=[], links=[])
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def main():
    if not (FRONTEND / "dist/index.html").is_file():
        raise SystemExit("Build the Spark frontend before running E2E")
    with tempfile.TemporaryDirectory(prefix="aoc-spark-e2e-") as directory:
        state = Path(directory)
        password, salt = secrets.token_urlsafe(24), secrets.token_hex(16)
        auth = state / "auth.json"
        auth.write_text(json.dumps({"salt": salt, "password_hash": password_hash(password, salt)}))
        auth.chmod(0o600)
        snapshot = state / "snapshot.json"
        write_snapshot(snapshot)
        # Keep the bound socket until the child inherits it: no free-port race.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            config = dict(auth_file=str(auth), database=str(state / "history.db"),
                          snapshot=str(snapshot), frontend=str(FRONTEND / "dist"),
                          control_socket=str(state / "no-hardware-control.sock"))
            config_path = state / "config.json"
            config_path.write_text(json.dumps(config))
            code = ("import json,sys,uvicorn; from aoc_spark.web import create_app; "
                    "uvicorn.run(create_app(json.load(open(sys.argv[1]))),fd=int(sys.argv[2]),"
                    "access_log=False,timeout_graceful_shutdown=2)")
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "apps/spark-platform/backend")}
            with (state / "server.log").open("w+") as log:
                process = subprocess.Popen([sys.executable, "-c", code, str(config_path), str(listener.fileno())],
                                           pass_fds=(listener.fileno(),), env=environment, stdout=log, stderr=log)
                stopped = threading.Event()
                def refresh():
                    while not stopped.wait(2):
                        write_snapshot(snapshot)
                thread = threading.Thread(target=refresh, daemon=True)
                thread.start()
                try:
                    base = f"http://127.0.0.1:{port}"
                    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    deadline = time.monotonic() + 20
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("E2E server exited before readiness")
                        try:
                            with http.open(base + "/api/v1/health", timeout=1) as response:
                                if json.load(response) == {"status": "ok", "collector": "ok"}:
                                    break
                        except OSError:
                            pass
                        if time.monotonic() >= deadline:
                            raise TimeoutError("E2E server readiness timed out")
                        time.sleep(.1)
                    environment.update(AOC_TEST_URL=base, AOC_TEST_PASSWORD=password)
                    for script in ("browser.mjs", "information.mjs", "parity.mjs"):
                        subprocess.run(["node", "tests/" + script], cwd=FRONTEND, env=environment, check=True, timeout=180)
                    print("Spark E2E passed against synthetic data; no hardware operations performed")
                except BaseException:
                    log.flush()
                    log.seek(0)
                    print(log.read(), file=sys.stderr)
                    raise
                finally:
                    stopped.set()
                    thread.join(timeout=5)
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    main()
