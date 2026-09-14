import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
import uuid

from aoc_spark.control import ControlServer, Executor, OPERATIONS, valid_task_id


class ControlExecutorTests(unittest.TestCase):
    def test_allowlist_maps_only_fixed_controller_arguments(self):
        self.assertEqual(set(OPERATIONS), {"start", "stop", "restart"})
        self.assertEqual(OPERATIONS["restart"], (("stop",), ("start",)))
        self.assertNotIn("shell", repr(OPERATIONS))
        identifier = str(uuid.uuid4())
        self.assertTrue(valid_task_id(identifier))
        self.assertFalse(valid_task_id("../unit.service"))

    def test_restart_progress_and_conflict(self):
        calls, messages = [], []
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            executor = Executor(root, runner=lambda args: calls.append(args))
            job = executor.begin(str(uuid.uuid4()), "restart")
            with self.assertRaisesRegex(RuntimeError, "operation_in_progress"):
                executor.begin(str(uuid.uuid4()), "start")
            executor.execute(job, messages.append)
            self.assertEqual(calls, [("stop",), ("start",)])
            self.assertEqual(messages[-1]["state"], "succeeded")
            self.assertEqual(executor.query(job.task_id)["state"], "succeeded")

    def test_cancel_is_applied_between_restart_steps(self):
        messages = []
        with tempfile.TemporaryDirectory() as root:
            executor = Executor(root)
            job = executor.begin(str(uuid.uuid4()), "restart")
            def runner(arguments):
                if arguments == ("stop",):
                    job.cancel.set()
            executor.runner = runner
            executor.execute(job, messages.append)
            self.assertEqual(messages[-1]["state"], "cancelled")
            self.assertEqual(messages[-1]["current_step"], "start")

    def test_runner_error_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as root:
            executor = Executor(root, runner=lambda _args: (_ for _ in ()).throw(RuntimeError("secret output")))
            job = executor.begin(str(uuid.uuid4()), "start")
            executor.execute(job, lambda _message: None)
            self.assertEqual(executor.query(job.task_id)["error"], "executor_step_failed")

    @unittest.skipIf(sys.platform == "darwin", "macOS application sandbox blocks Unix-domain bind")
    def test_unix_protocol_accepts_only_structured_fixed_action(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            path = str(Path(root) / "control.sock")
            calls = []
            server = ControlServer(path, Executor(Path(root) / "jobs", runner=lambda args: calls.append(args)), os.getuid())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                identifier = str(uuid.uuid4())
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(path)
                    client.sendall((json.dumps({"command": "run", "task_id": identifier,
                                                "action": "start"}) + "\n").encode())
                    states = [json.loads(line)["state"] for line in client.makefile()]
                self.assertEqual(states[-1], "succeeded")
                self.assertEqual(calls, [("start",)])
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(path)
                    client.sendall((json.dumps({"command": "run", "task_id": str(uuid.uuid4()),
                                                "action": "start", "argv": ["sh"]}) + "\n").encode())
                    self.assertEqual(json.loads(client.makefile().readline())["error"], "invalid_request")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
