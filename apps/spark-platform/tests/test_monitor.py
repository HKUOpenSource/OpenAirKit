import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from aoc_spark.collector import n2_associated
from aoc_spark.domain import SCHEMA_VERSION, fresh_snapshot, observation, rate, utc
from aoc_spark.storage import Store
from aoc_spark.web import create_app, password_hash, redacted_diagnostics


class ObservationTests(unittest.TestCase):
    def test_contract_version_and_quality_reason(self):
        self.assertEqual(SCHEMA_VERSION, 4)
        self.assertEqual(observation('ran', 'ocudu', 'cqi', status='unavailable')['reason'], 'sample_unavailable')
        with self.assertRaises(ValueError):
            observation('ran', 'ocudu', 'cqi', status='healthy')

    def test_counter_reset_and_window(self):
        self.assertIsNone(rate(100, 10, 5))
        self.assertIsNone(rate(100, 200, 0))
        self.assertEqual(rate(100, 200, 5), 160)

    def test_expired_samples_keep_unsupported(self):
        sample = {"observed_at": "2000-01-01T00:00:00+00:00", "observations": [
            {**observation("ran", "ocudu", "n2", True), "observed_at": "2000-01-01T00:00:00+00:00"},
            observation("sessions", "ocudu:oai", "observed_5qi", status="unsupported", reason="adapter_pending")]}
        expired = fresh_snapshot(sample)
        self.assertEqual(expired["collector_status"], "stale")
        self.assertEqual(expired["active_stack"], "unknown")
        self.assertEqual(expired["observations"][0]["status"], "stale")
        self.assertEqual(expired["observations"][1]["status"], "unsupported")

    def test_exact_v2_sctp_association(self):
        self.assertFalse(n2_associated("ESTAB 192.168.70.129:3000 192.168.70.132:38412", "172.28.81.1", "172.28.81.12"))
        self.assertTrue(n2_associated("ESTAB 172.28.81.1%aoc-v2:123 172.28.81.12:38412", "172.28.81.1", "172.28.81.12"))
        self.assertFalse(n2_associated("ESTAB 172.28.81.11:123 172.28.81.12:38412", "172.28.81.1", "172.28.81.12"))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        auth = root / "auth.json"
        auth.write_text(json.dumps({"salt": "12" * 16, "password_hash": password_hash("test-password", "12" * 16)}))
        (root / "index.html").write_text("test")
        self.snapshot = root / "snapshot.json"
        self.snapshot.write_text(json.dumps(dict(schema_version=SCHEMA_VERSION, observed_at=utc(), collector_status="ok",
                                                 active_stack="ocudu", observations=[], services=[], events=[], devices=[])))
        self.app = create_app(dict(auth_file=str(auth), database=str(root / "history.db"),
                                   snapshot=str(self.snapshot), frontend=str(root), retention_days=7))
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def login(self):
        response = self.client.post("/api/v1/login", json={"password": "test-password"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        return response.json()["csrf"]

    def test_health_auth_and_single_stack_contract(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        for path in ("snapshot", "diagnostics", "history", "events", "audit", "devices"):
            self.assertEqual(self.client.get("/api/v1/" + path).status_code, 401)
        self.login()
        session = self.client.get("/api/v1/session").json()
        self.assertEqual(set(session), {"csrf"})
        self.assertEqual(self.client.get("/api/v1/snapshot").json()["active_stack"], "ocudu")
        self.assertEqual(self.client.get("/api/v1/devices?stack=legacy").status_code, 422)

    def test_diagnostics_redacts_identifiers_and_component_route(self):
        self.login()
        sample = dict(schema_version=SCHEMA_VERSION, observed_at=utc(), collector_status="ok",
                      active_stack="ocudu", observations=[], services=[], events=[], devices=[],
                      components=[dict(id="ocudu:amf", stack="ocudu", name="AMF", kind="nf",
                                       state="running", details={"pid": 42, "address": "172.28.81.12"},
                                       observed_at=utc(), metrics=[])], links=[])
        self.snapshot.write_text(json.dumps(sample))
        export = self.client.get("/api/v1/diagnostics")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.json()["components"][0]["details"],
                         {"pid": "<redacted>", "address": "<redacted>"})
        self.assertEqual(self.client.get("/components/ocudu%3Aamf").text, "test")
        self.assertEqual(self.client.get("/api/v1/components/ocudu%3Aamf").json()["name"], "AMF")

    def test_recursive_diagnostic_redaction(self):
        result = redacted_diagnostics({"nested": [{"supi": "imsi-secret", "state": "active"}]})
        self.assertEqual(result, {"nested": [{"supi": "<redacted>", "state": "active"}]})

    def test_no_cross_stack_switch_or_ims_surface(self):
        self.login()
        self.assertIn(self.client.get("/api/v1/switch").status_code, (404, 405))
        self.assertIn(self.client.post("/api/v1/switch", json={}).status_code, (404, 405))
        self.assertEqual(self.client.get("/ims").status_code, 404)
        self.assertEqual(self.client.get("/devices/example").text, "test")

    def test_login_logout_limits_and_invalid_snapshot(self):
        csrf = self.login()
        self.assertEqual(self.client.post("/api/v1/logout").status_code, 403)
        self.snapshot.write_text("broken")
        self.assertEqual(self.client.get("/api/v1/snapshot").json()["collector_status"], "unavailable")
        self.assertEqual(self.client.get("/api/v1/history?limit=10000000").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/health", headers={"host": "evil.test"}).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/logout", headers={"X-CSRF-Token": csrf}).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/snapshot").status_code, 401)

    def test_successful_logins_do_not_consume_failure_limit(self):
        for _ in range(6):
            self.assertEqual(self.client.post("/api/v1/login", json={"password": "test-password"}).status_code, 200)

    def test_invalid_logins_are_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.client.post("/api/v1/login", json={"password": "wrong-password"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/login", json={"password": "wrong-password"}).status_code, 429)

    def test_expired_session_is_rejected(self):
        self.login()
        with self.app.state.store.connect() as db:
            db.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
        self.assertEqual(self.client.get("/api/v1/snapshot").status_code, 401)

    def test_control_requires_csrf_allowlisted_shape_and_rejects_concurrency(self):
        csrf = self.login()
        body = {"action": "restart", "confirmation": True}
        self.assertEqual(self.client.post("/api/v1/control", json=body).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/control", headers={"X-CSRF-Token": csrf},
                                          json={**body, "command": "anything"}).status_code, 422)
        created = self.client.post("/api/v1/control", headers={"X-CSRF-Token": csrf}, json=body)
        self.assertEqual(created.status_code, 200)
        identifier = created.json()["id"]
        self.assertEqual(self.client.get("/api/v1/control/" + identifier).status_code, 200)
        self.app.state.store.update_control(identifier, {"state": "running"})
        conflict = self.client.post("/api/v1/control", headers={"X-CSRF-Token": csrf}, json=body)
        self.assertEqual(conflict.status_code, 409)

    def test_database_backup_and_deduplication(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / "data.db")
            sample = dict(observed_at=utc(), devices=[], events=[])
            store.ingest(sample)
            store.ingest(sample)
            self.assertEqual(len(store.history(10)), 1)
            store.backup(Path(root) / "backup.db")
            self.assertEqual(Store(Path(root) / "backup.db").history(10), [sample])

    def test_v3_migration_backup_and_split_retention(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "data.db"
            with sqlite3.connect(path) as db:
                db.executescript("""
                    CREATE TABLE snapshots(at TEXT PRIMARY KEY, inserted REAL NOT NULL, body TEXT NOT NULL);
                    CREATE TABLE events(id TEXT PRIMARY KEY, at TEXT NOT NULL, body TEXT NOT NULL);
                    CREATE TABLE sessions(token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                    CREATE TABLE audit(id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
                    CREATE TABLE entities(id TEXT PRIMARY KEY, kind TEXT NOT NULL, stack TEXT NOT NULL, at TEXT NOT NULL, body TEXT NOT NULL);
                    CREATE TABLE entity_samples(id TEXT NOT NULL, at TEXT NOT NULL, stack TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(id,at));
                    PRAGMA user_version=3;
                """)
            store = Store(path)
            self.assertEqual(sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertEqual(len(list(Path(root).glob("data.db.before-v5-*.db"))), 1)
            twenty_days = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - 20 * 86400))
            event = {"id": "retained", "at": twenty_days, "stack": "ocudu", "kind": "test", "message": "kept"}
            with store.connect() as db:
                db.execute("INSERT INTO events VALUES(?,?,?)", (event["id"], event["at"], json.dumps(event)))
                db.execute("INSERT INTO audit(at,action,detail) VALUES(?,?,?)", (time.time() - 20 * 86400, "test", "kept"))
                db.execute("INSERT INTO entity_samples VALUES(?,?,?,?)", ("old", twenty_days, "ocudu", "{}"))
            store.ingest({"observed_at": utc(), "devices": [], "events": []})
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM events WHERE id='retained'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE detail='kept'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM entity_samples WHERE id='old'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
