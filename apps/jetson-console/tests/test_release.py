import importlib.util
from pathlib import Path
import tempfile
import unittest

from scripts.jetson_release import build


ROOT = Path(__file__).resolve().parents[3]


def load_manage(path):
    specification = importlib.util.spec_from_file_location("v2_jetson_manage_test", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def test_release_contains_only_v2_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = root / "wheels"
            wheels.mkdir()
            (wheels / "fixture.whl").write_bytes(b"fixture")
            release = root / "release"
            build(release, wheels)
            manifest = load_manage(release / "deploy/manage.py").verify(release)
            names = set(manifest["files"])
            self.assertIn("backend/aoc_jetson/agent.py", names)
            self.assertIn("frontend/index.html", names)
            self.assertNotIn("backend/aoc_jetson_v1/agent.py", names)
            self.assertFalse(any("retired-integration" in name.lower() for name in names))

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
