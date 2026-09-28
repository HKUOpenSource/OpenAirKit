"""Root control executor for the independent V2 stack.

The socket protocol deliberately has no argv, shell, unit, container, target, or
path field. Every accepted action maps to a reviewed constant command.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import socket
import socketserver
import stat
import struct
import subprocess
import threading
import time
import uuid


OPERATIONS = {
    "start": (("start",),),
    "stop": (("stop",),),
    "restart": (("stop",), ("start",)),
}
FINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


def valid_task_id(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def run_step(arguments, timeout=420):
    executable = Path("/usr/local/bin/aoc-v2ctl")
    resolved = executable.resolve(strict=True)
    if Path("/opt/agentic-ocudu/v2") not in resolved.parents:
        raise RuntimeError("controller_path_outside_v2_release")
    for path in (executable, resolved):
        metadata = path.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise RuntimeError("controller_integrity_failed")
    result = subprocess.run([str(executable), *arguments], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=timeout)
    if result.returncode:
        raise RuntimeError("controller_exit_%d" % result.returncode)


class Job:
    def __init__(self, task_id, action):
        self.task_id, self.action = task_id, action
        self.cancel = threading.Event()
        self.status = {"task_id": task_id, "action": action, "state": "queued",
                       "current_step": None, "error": None, "updated_at": time.time()}


class Executor:
    def __init__(self, state_directory, runner=run_step):
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.jobs = {}
        self.lock = threading.RLock()

    def persist(self, job):
        with self.lock:
            job.status["updated_at"] = time.time()
            temporary = self.state_directory / (job.task_id + ".tmp")
            temporary.write_text(json.dumps(job.status, sort_keys=True) + "\n")
            os.chmod(temporary, 0o640)
            temporary.replace(self.state_directory / (job.task_id + ".json"))

    def emit(self, job, send, **changes):
        with self.lock:
            job.status.update(changes)
            self.persist(job)
            message = dict(job.status)
        # A slow/disconnected client must not hold up cancellation or queries.
        send(message)

    def begin(self, task_id, action):
        with self.lock:
            if any(job.status["state"] not in FINAL_STATES for job in self.jobs.values()):
                raise RuntimeError("operation_in_progress")
            job = Job(task_id, action)
            self.persist(job)
            self.jobs[task_id] = job
            return job

    def execute(self, job, send):
        try:
            self.emit(job, send, state="running")
            for arguments in OPERATIONS[job.action]:
                step = arguments[0]
                if job.cancel.is_set():
                    self.emit(job, send, state="cancelled", current_step=step,
                              error="cancelled_at_step_boundary")
                    return
                self.emit(job, send, state="running", current_step=step,
                          step={"name": step, "state": "running", "at": time.time()})
                self.runner(arguments)
                self.emit(job, send, state="running", current_step=step,
                          step={"name": step, "state": "succeeded", "at": time.time()})
            self.emit(job, send, state="succeeded", current_step=None)
        except Exception as error:
            message = str(error)
            if not message.startswith(("controller_", "cancelled_")):
                message = "executor_step_failed"
            self.emit(job, send, state="failed", error=message)

    def query(self, task_id):
        with self.lock:
            job = self.jobs.get(task_id)
            if job:
                return dict(job.status)
        path = self.state_directory / (task_id + ".json")
        return json.loads(path.read_text()) if path.exists() else {
            "task_id": task_id, "state": "unknown", "error": "executor_task_unknown"}

    def request_cancel(self, task_id):
        with self.lock:
            job = self.jobs.get(task_id)
            if not job:
                return {"task_id": task_id, "state": "unknown", "error": "executor_task_unknown"}
            if job.status["state"] not in FINAL_STATES:
                job.cancel.set()
                job.status["state"] = "cancel_requested"
                self.persist(job)
            return dict(job.status)


class ControlServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, socket_path, executor, allowed_uid):
        self.executor, self.allowed_uid = executor, allowed_uid
        super().__init__(socket_path, ControlHandler)


class ControlHandler(socketserver.StreamRequestHandler):
    def send(self, value):
        try:
            self.wfile.write(json.dumps(value, separators=(",", ":")).encode() + b"\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle(self):
        credentials = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", credentials)
        if uid != self.server.allowed_uid:
            self.send({"state": "rejected", "error": "peer_not_allowed"})
            return
        raw = self.rfile.readline(2049)
        if len(raw) > 2048 or not raw.endswith(b"\n"):
            self.send({"state": "rejected", "error": "invalid_request"})
            return
        try:
            request = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            self.send({"state": "rejected", "error": "invalid_request"})
            return
        command, task_id = request.get("command"), request.get("task_id")
        expected = {"command", "task_id", "action"} if command == "run" else {"command", "task_id"}
        if set(request) != expected or command not in {"run", "query", "cancel"} or not valid_task_id(task_id):
            self.send({"state": "rejected", "error": "invalid_request"})
            return
        if command == "query":
            self.send(self.server.executor.query(task_id))
        elif command == "cancel":
            self.send(self.server.executor.request_cancel(task_id))
        elif request.get("action") not in OPERATIONS:
            self.send({"state": "rejected", "error": "invalid_action"})
        else:
            try:
                job = self.server.executor.begin(task_id, request["action"])
            except RuntimeError as error:
                self.send({"task_id": task_id, "state": "conflict", "error": str(error)})
                return
            self.server.executor.execute(job, self.send)


def serve(socket_path, state_directory, allowed_user="aoc-web"):
    path = Path(socket_path)
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise RuntimeError("control_socket_path_is_not_a_socket")
        path.unlink()
    server = ControlServer(str(path), Executor(state_directory), pwd.getpwnam(allowed_user).pw_uid)
    os.chmod(path, 0o660)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/run/aoc-control/control.sock")
    parser.add_argument("--state-directory", default="/run/aoc-control/jobs")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("control executor must run as root")
    serve(args.socket, args.state_directory)


if __name__ == "__main__":
    main()
