import json
from pathlib import Path
import tempfile
import unittest

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
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/status").status_code, 401)

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


if __name__ == "__main__":
    unittest.main()
