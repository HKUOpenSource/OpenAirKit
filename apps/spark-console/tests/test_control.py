import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

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

    def test_progress_and_cancel_serialize_persistence(self):
        with tempfile.TemporaryDirectory() as root:
            cancel_done, cancel_started, writing, release_write = (threading.Event() for _ in range(4))
            calls, errors = [], []
            def runner(arguments):
                calls.append(arguments)
                self.assertTrue(cancel_done.wait(3))
            executor = Executor(root, runner=runner)
            job = executor.begin(str(uuid.uuid4()), "restart")
            write = Path.write_text
            def paused_write(path, *args, **kwargs):
                result = write(path, *args, **kwargs)
                if threading.current_thread().name == "progress" and not writing.is_set():
                    writing.set()
                    if not release_write.wait(3):
                        raise TimeoutError("Test write was not released")
                return result
            def execute():
                try:
                    executor.execute(job, lambda _: None)
                except Exception as error:
                    errors.append(error)
            def cancel():
                cancel_started.set()
                try:
                    executor.request_cancel(job.task_id)
                except Exception as error:
                    errors.append(error)
                finally:
                    cancel_done.set()
            progress = threading.Thread(target=execute, name="progress")
            cancellation = threading.Thread(target=cancel)
            with patch.object(Path, "write_text", paused_write):
                try:
                    progress.start()
                    self.assertTrue(writing.wait(3))
                    cancellation.start()
                    self.assertTrue(cancel_started.wait(3))
                    self.assertFalse(cancel_done.wait(.1), "Cancel raced an unfinished progress write")
                finally:
                    release_write.set()
                    progress.join(4)
                    if cancellation.ident is not None:
                        cancellation.join(4)
            self.assertFalse(progress.is_alive())
            self.assertFalse(cancellation.is_alive())
            self.assertEqual(errors, [])
            self.assertIn(calls, ([], [("stop",)]))
            self.assertEqual(executor.query(job.task_id)["state"], "cancelled")
            self.assertEqual(json.loads((Path(root) / (job.task_id + ".json")).read_text())["state"], "cancelled")
            executor.begin(str(uuid.uuid4()), "start")

    def test_failed_initial_persistence_does_not_strand_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            executor = Executor(root, runner=lambda _: self.fail("Must not run after failed initial emission"))
            job = executor.begin(str(uuid.uuid4()), "start")
            persist = executor.persist
            attempts = []
            def fail_once(value):
                attempts.append(value)
                if len(attempts) == 1:
                    raise OSError("Synthetic write failure")
                persist(value)
            with patch.object(executor, "persist", side_effect=fail_once):
                executor.execute(job, lambda _: None)
            self.assertEqual(executor.query(job.task_id)["state"], "failed")
            executor.begin(str(uuid.uuid4()), "stop")

    def test_failed_begin_does_not_reserve_a_job(self):
        with tempfile.TemporaryDirectory() as root:
            executor = Executor(root)
            with patch.object(executor, "persist", side_effect=OSError("Synthetic write failure")):
                with self.assertRaises(OSError):
                    executor.begin(str(uuid.uuid4()), "start")
            executor.begin(str(uuid.uuid4()), "start")

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
