import importlib.util
import hashlib
import json
import os
import sqlite3
from types import SimpleNamespace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.jetson_release import build


ROOT = Path(__file__).resolve().parents[3]


def load_manage(path):
    specification = importlib.util.spec_from_file_location("v2_jetson_manage_test", path)
    module = importlib.util.module_from_spec(specification)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        specification.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class ReleaseTests(unittest.TestCase):
    def installed_fixture(self, root):
        release = root / "releases/reviewed"
        release.mkdir(parents=True)
        (release / "module.py").write_text("reviewed source")
        manifest = {"files": {"module.py": hashlib.sha256(b"reviewed source").hexdigest()}}
        (release / "manifest.json").write_text(json.dumps(manifest))
        (release / "venv/bin").mkdir(parents=True)
        (release / "venv/bin/python").write_text("runtime fixture")
        return release, manifest

    def root_metadata(self):
        lstat = Path.lstat
        def owned(path):
            values = list(lstat(path))
            values[4] = values[5] = 0
            return os.stat_result(values)
        return patch.object(Path, "lstat", owned)

    def test_existing_release_reuse_checks_code_and_generated_runtime(self):
        manage = load_manage(ROOT / "deploy/jetson/manage.py")
        with tempfile.TemporaryDirectory() as temporary, self.root_metadata():
            release, manifest = self.installed_fixture(Path(temporary).resolve())
            (release / "__pycache__").mkdir()
            (release / "__pycache__/module.cpython-310.pyc").write_bytes(b"generated cache")
            manage.verify_installed(release, manifest)
            (release / "module.py").write_text("modified source")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                manage.verify_installed(release, manifest)

    def test_existing_release_rejects_injected_code_and_writable_runtime(self):
        manage = load_manage(ROOT / "deploy/jetson/manage.py")
        with tempfile.TemporaryDirectory() as temporary, self.root_metadata():
            release, manifest = self.installed_fixture(Path(temporary).resolve())
            extra = release / "injected.py"
            extra.write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "package contents"):
                manage.verify_installed(release, manifest)
            extra.unlink()
            (release / "venv/bin/python").chmod(0o666)
            with self.assertRaisesRegex(ValueError, "Unprotected"):
                manage.verify_installed(release, manifest)

    def test_reinstall_runtime_failure_preserves_existing_release(self):
        manage = load_manage(ROOT / "deploy/jetson/manage.py")
        with tempfile.TemporaryDirectory() as temporary, self.root_metadata():
            root = Path(temporary).resolve()
            release, manifest = self.installed_fixture(root)
            manifest["release"] = release.name
            (release / "manifest.json").write_text(json.dumps(manifest))
            etc = root / "etc"
            etc.mkdir()
            (etc / "web.json").write_text("{}")
            with patch.multiple(manage, BASE=root, ETC=etc), \
                    patch.object(manage, "verify", return_value=manifest), \
                    patch.object(manage, "unit_state", return_value="inactive"), \
                    patch.object(manage, "preflight", return_value={}), \
                    patch.object(manage, "backup", return_value=root / "checkpoint"), \
                    patch.object(manage, "output", side_effect=RuntimeError("broken dependencies")):
                with self.assertRaisesRegex(RuntimeError, "broken dependencies"):
                    manage.install(root / "stage")
            self.assertTrue((release / "module.py").is_file())
            self.assertTrue((release / "venv/bin/python").is_file())

    def test_release_contains_only_v2_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = root / "wheels"
            wheels.mkdir()
            (wheels / "fixture.whl").write_bytes(b"fixture")
            release = root / "release"
            # Boundary fixture; real wheel tags, completeness and metadata have
            # separate behavioral coverage in tests/test_release_tools.py.
            with patch('scripts.jetson_release.validate_wheels'):
                build(release, wheels)
            manifest = load_manage(release / "deploy/manage.py").verify(release)
            names = set(manifest["files"])
            self.assertIn("backend/aoc_jetson/agent.py", names)
            self.assertIn("frontend/index.html", names)
            self.assertNotIn("backend/aoc_jetson_v1/agent.py", names)
            self.assertFalse(any("retired-integration" in name.lower() for name in names))

    def test_rollback_restores_pre_migration_config_and_database(self):
        from aoc_jetson.store import Store
        manage = load_manage(ROOT / "deploy/jetson/manage.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths = {name: root / name.lower() for name in ("BASE", "ETC", "STATE", "WEB_STATE")}
            with patch.multiple(manage, **paths), patch.object(manage, "stop"), \
                    patch.object(manage, "output"), patch.object(manage.os, "chown"), \
                    patch.object(manage.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1, pw_gid=1)):
                for path in paths.values():
                    path.mkdir()
                old = paths["BASE"] / "releases/old"
                old.mkdir(parents=True)
                (paths["BASE"] / "current").symlink_to(old)
                (paths["ETC"] / "device.json").write_text(json.dumps({"schema_version": 2}))
                store = Store(paths["STATE"] / "device.db")
                job = store.new_job("speed", "old", ["Download"], {})
                with store.connect() as db:
                    db.execute("PRAGMA user_version=1")
                record = manage.backup()
                Store(store.path)
                (paths["ETC"] / "device.json").write_text(json.dumps({"schema_version": 3}))
                manage.rollback(record.name)
                self.assertEqual(json.loads((paths["ETC"] / "device.json").read_text())["schema_version"], 2)
                with sqlite3.connect(store.path) as db:
                    self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
                    restored = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])
                self.assertNotIn("retired", restored)
                self.assertEqual((paths["BASE"] / "current").resolve(), old)

    def test_units_are_v2_named_bounded_and_disabled_by_default(self):
        device = (ROOT / "deploy/jetson/aoc-v2-jetson-device.service").read_text()
        web = (ROOT / "deploy/jetson/aoc-v2-jetson-web.service").read_text()
        device_entry = (ROOT / "deploy/jetson/device_entry.py").read_text()
        web_entry = (ROOT / "deploy/jetson/web_entry.py").read_text()
        network_entry = (ROOT / "deploy/jetson/network_entry.py").read_text()
        manager = (ROOT / "deploy/jetson/manage.py").read_text()
        self.assertIn("device_entry.py", device)
        self.assertIn("TimeoutStopSec=60", device)
        self.assertIn("web_entry.py", web)
        self.assertIn("from aoc_jetson.agent import main", device_entry)
        self.assertIn("from aoc_jetson.api import main", web_entry)
        self.assertIn("from aoc_jetson.network import main", network_entry)
        self.assertNotIn("PYTHONPATH=", device + web)
        self.assertNotIn("systemctl\", \"enable", manager)
        self.assertIn('"device_started": False', manager)
        self.assertIn("socket.SO_REUSEADDR", manager)

    def test_site_guard_checks_real_controllers_and_serial_owner(self):
        guard = (ROOT / "deploy/jetson/site_guard.py").read_text()
        self.assertIn("oai-console.service", guard)
        self.assertIn("aoc-jetson-agent.service", guard)
        self.assertIn('["fuser", port]', guard)


if __name__ == "__main__":
    unittest.main()
