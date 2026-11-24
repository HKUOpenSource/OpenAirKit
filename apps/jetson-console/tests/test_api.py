import asyncio
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from aoc_jetson.agent import Agent, Conflict
from aoc_jetson.api import create_app, password_record, redacted
from aoc_jetson.config import validate
from aoc_jetson.simulator import SimModem, SimNetwork


ROOT = Path(__file__).resolve().parents[3]


def fixture(directory):
    value = json.loads((ROOT / "config" / "jetson.example.json").read_text())
    value.update(state_dir=str(Path(directory) / "state"),
                 web_state_dir=str(Path(directory) / "web"),
                 agent_socket=str(Path(directory) / "device.sock"),
                 commissioned=True, management_verified=True,
                 sim_sha256="0" * 64, simulation=True)
    return validate(value)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.config = fixture(self.temporary.name)
        self.agent = Agent(self.config, Path(self.temporary.name) / "config.json",
                           SimModem(), SimNetwork())
        self.agent.set_maintenance(False)
        frontend = Path(self.temporary.name) / "frontend"
        frontend.mkdir()
        (frontend / "index.html").write_text("<!doctype html><title>V2</title>")
        web = {**self.config, "frontend_dir": str(frontend),
               "password_hash": password_record("Independent-Console-2026")}

        async def transport(payload):
            try:
                return self.agent.dispatch(payload)
            except Conflict as error:
                raise HTTPException(409, str(error)) from error
            except (ValueError, KeyError) as error:
                raise HTTPException(400, str(error)) from error

        self.client = TestClient(create_app(web, transport))
        self.addCleanup(self.client.close)

    def login(self):
        response = self.client.post("/api/v1/auth/login",
                                    json={"password": "Independent-Console-2026"})
        self.assertEqual(response.status_code, 200)
        return {"x-csrf-token": response.json()["csrf"]}

    def test_health_is_public_and_device_failure_does_not_fail_web_health(self):
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.headers.get("x-frame-options"), "DENY")
        self.assertEqual(self.client.get("/api/v1/status").status_code, 401)

    def test_untrusted_host_and_body_size_limits(self):
        self.assertEqual(
            self.client.get("/api/v1/health", headers={"host": "evil.example"}).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/login", headers={"content-length": "abc"}, content=b"").status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/login", json={"password": "x" * 9000}).status_code,
            413,
        )

    def test_login_csrf_origin_and_logout(self):
        headers = self.login()
        self.assertEqual(self.client.get("/api/v1/config").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/maintenance", json={"enabled": True}).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/maintenance", headers={**headers, "origin": "https://invalid.example"},
                                          json={"enabled": True}).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/status").status_code, 401)

    def test_api_has_no_environment_or_profile_contract(self):
        headers = self.login()
        self.assertEqual(self.client.get("/api/v1/environments").status_code, 404)
        response = self.client.post("/api/v1/jobs", headers=headers,
                                    json={"kind": "setup", "profile": "legacy-oai",
                                          "revision": self.config["revision"]})
        self.assertEqual(response.status_code, 422)

    def test_task_validation_and_diagnostics_redaction(self):
        headers = self.login()
        bad = self.client.post("/api/v1/jobs", headers=headers,
                               json={"kind": "shell", "revision": self.config["revision"]})
        self.assertEqual(bad.status_code, 422)
        retired = self.client.post("/api/v1/jobs", headers=headers, json={"kind": "speed", "revision": self.config["revision"]})
        self.assertEqual(retired.status_code, 422)
        self.agent.sample(True)
        report = self.client.get("/api/v1/diagnostics").json()
        encoded = json.dumps(report)
        self.assertNotIn("sim_sha256", encoded)
        self.assertNotIn("192.168.225.88", encoded)
        self.assertNotIn("10.0.0.2", encoded)
        self.assertIn("connected", report["status"])

    def test_history_and_metric_windows_are_bounded(self):
        self.login()
        self.assertEqual(self.client.get("/api/v1/history?hours=721").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/metrics?hours=169").status_code, 400)

    def test_redaction_is_recursive(self):
        value = redacted({"source": "secret", "nested": [{"address": "secret", "state": "ok"}]})
        self.assertEqual(value, {"nested": [{"state": "ok"}]})

    def stream_request(self):
        endpoint = next(route.endpoint for route in self.client.app.routes
                        if getattr(route, "path", None) == "/api/v1/events/stream")
        request = SimpleNamespace(cookies=dict(self.client.cookies),
                                  is_disconnected=AsyncMock(return_value=False))
        return endpoint, request

    def test_stream_survives_multiple_old_lifetimes_and_recovers_executor_errors(self):
        self.login()
        self.agent.sample(True)
        endpoint, request = self.stream_request()
        elapsed = 0

        async def sleep(seconds):
            nonlocal elapsed
            elapsed += seconds

        async def check():
            response = await endpoint(request)
            self.assertEqual(response.headers["cache-control"], "no-cache")
            iterator = response.body_iterator
            self.assertEqual(await anext(iterator), "retry: 1000\n\n")
            try:
                for _ in range(25):
                    self.assertIn("event: status", await anext(iterator))
                self.assertGreaterEqual(elapsed, 48)
                with patch.object(self.agent, "dispatch", side_effect=HTTPException(503, "Unavailable")):
                    self.assertIn("event: unavailable", await anext(iterator))
                self.assertIn("event: status", await anext(iterator))
                request.is_disconnected.return_value = True
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
            finally:
                await iterator.aclose()

        clock = Mock(wraps=time)
        clock.monotonic.side_effect = lambda: elapsed
        with patch("aoc_jetson.api.asyncio.sleep", side_effect=sleep), patch("aoc_jetson.api.time", clock):
            asyncio.run(check())

    def test_live_stream_stops_after_logout(self):
        headers = self.login()
        endpoint, request = self.stream_request()

        async def check():
            iterator = (await endpoint(request)).body_iterator
            try:
                await anext(iterator)  # retry interval
                self.assertIn("event: status", await anext(iterator))
                self.client.post("/api/v1/auth/logout", headers=headers)
                self.assertIn("event: expired", await anext(iterator))
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
            finally:
                await iterator.aclose()

        with patch("aoc_jetson.api.asyncio.sleep", new=AsyncMock()):
            asyncio.run(check())

    def test_expiry_during_executor_call_does_not_publish_status(self):
        headers = self.login()
        endpoint, request = self.stream_request()

        def expired_call(payload):
            self.client.post("/api/v1/auth/logout", headers=headers)
            return {"connected": True}

        async def check():
            iterator = (await endpoint(request)).body_iterator
            try:
                await anext(iterator)
                with patch.object(self.agent, "dispatch", side_effect=expired_call):
                    self.assertIn("event: expired", await anext(iterator))
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
            finally:
                await iterator.aclose()

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
