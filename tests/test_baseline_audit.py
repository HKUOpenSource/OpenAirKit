import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("baseline_audit", ROOT / "deploy/coexistence/audit_jetson_baseline.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class BaselineAuditTests(unittest.TestCase):
    def test_config_is_allowlisted_and_does_not_export_credentials(self):
        source = {"modem": {"expected_plmn": "46003", "expected_imsi": "private identity"},
                  "auth": {"admin_password_hash": "private hash"}, "core": {"key": "private key"}}
        self.assertEqual(audit.config_view(source), {"expected_plmn": "46003"})

    def test_snapshot_omits_identity_auth_and_raw_modem_responses(self):
        value = {"device": {"imsi": "secret", "pdu_address": "10.0.0.2"},
                 "registration": {"registered": True, "raw": "secret"},
                 "data_plane": {"usable": True}, "credentials": "secret"}
        result = audit.snapshot_view(value)
        self.assertNotIn("secret", json.dumps(result))
        self.assertTrue(result["data_plane"]["usable"])

    def test_database_read_is_unchanged_and_stale_samples_marked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE settings(key TEXT,value TEXT); CREATE TABLE jobs(state TEXT);"
                                 "CREATE TABLE speed_tests(state TEXT); CREATE TABLE metrics(id INTEGER,created_at REAL,snapshot TEXT);")
                db.execute("INSERT INTO settings VALUES ('maintenance_mode','false')")
                db.execute("INSERT INTO settings VALUES ('admin_password_hash','private')")
                db.execute("INSERT INTO metrics VALUES (1,1,?)", (json.dumps({"device": {"imsi": "secret"}}),))
            before = path.read_bytes()
            report = audit.database_view(path, 100)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(report["samples"][0]["fresh"])
            self.assertNotIn("secret", json.dumps(report))
            self.assertNotIn("private", json.dumps(report))

    def test_missing_restoration_report_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            with self.assertRaisesRegex(ValueError, "No completed"):
                audit.restoration_view(p, p / "config", p / "helper", p / "state", p / "guard")

    def test_restoration_requires_current_code_config_and_helper_to_match(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            original = p / "backups/dual-env-1"
            saved = p / "backups/before-original-restore-1"
            saved.mkdir(parents=True)
            for base in (p, original):
                (base / "backend/oai_console").mkdir(parents=True)
                (base / "backend/oai_console/main.py").write_text("baseline")
                (base / "frontend").mkdir()
                (base / "frontend/index.html").write_text("baseline")
            for name in ("config.toml", "helper"):
                (original / name).write_text("baseline")
                (p / name).write_text("baseline")
            evidence = {key: audit.file_map(original / key) for key in ("backend", "frontend")}
            evidence.update(config_sha256=audit.sha(p / "config.toml"), helper_sha256=audit.sha(p / "helper"))
            (saved / "release.json").write_text(json.dumps({"base": audit.BASE, "base_backend": evidence["backend"]}))
            (saved / "restoration-result.json").write_text(json.dumps({"base": audit.BASE, "evidence": evidence,
                "original_backup": "dual-env-1", "history_preserved": True}))
            view = lambda: audit.restoration_view(p, p / "config.toml", p / "helper", p / "state", p / "guard")
            self.assertTrue(view()["passed"])
            (p / "helper").write_text("modified")
            self.assertFalse(view()["passed"])
            self.assertFalse(view()["checks"]["helper_matches"])

    def test_recent_database_row_does_not_make_old_observation_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE settings(key TEXT,value TEXT); CREATE TABLE jobs(state TEXT);"
                                 "CREATE TABLE speed_tests(state TEXT); CREATE TABLE metrics(id INTEGER,created_at REAL,snapshot TEXT);")
                db.execute("INSERT INTO metrics VALUES (1,100,?)", (json.dumps({"at": 1}),))
            self.assertFalse(audit.database_view(path, 101)["samples"][0]["fresh"])


if __name__ == "__main__":
    unittest.main()
