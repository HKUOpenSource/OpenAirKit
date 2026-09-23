import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aoc_jetson.config import DEVICE, REFERENCE, SELECTION, DIAGNOSTICS, RECOVERY, migrate, validate
from aoc_jetson.network import HELPER_ENTRY, Network, helper


def configuration(root):
    return validate({"schema_version": 3, "name": "agentic-ocudu-jetson-v2",
                     "selection": copy.deepcopy(SELECTION), "diagnostics": copy.deepcopy(DIAGNOSTICS),
            "recovery": copy.deepcopy(RECOVERY), "network": copy.deepcopy(REFERENCE), "device": copy.deepcopy(DEVICE),
                     "management": {"wifi_interface": "wifi0", "tailscale_interface": "tailscale0",
                                    "spark_address": "192.0.2.20"},
                     "state_dir": str(root), "web_state_dir": str(root / "web"),
                     "agent_socket": str(root / "run.sock"), "commissioned": True,
                     "management_verified": True, "sim_sha256": "0" * 64})


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = configuration(self.root)
        self.state = {"data_interface": "rndis0", "data_address": "192.168.225.29",
                      "wifi_interface": "wifi0", "wifi_address": "192.0.2.2",
                      "tailscale_interface": "tailscale0"}

    def test_arbitrary_probe_and_action_are_rejected(self):
        network = Network(self.config, "config")
        with self.assertRaises(ValueError):
            network.probe("1.2.3.4")
        with self.assertRaises(ValueError):
            network.action("shell")

    @patch("aoc_jetson.network.os.geteuid", return_value=0)
    @patch("aoc_jetson.network.inspect")
    @patch("aoc_jetson.network.route_to")
    def test_prepare_accepts_existing_bound_routes_without_mutation(self, route, inspect_mock, _euid):
        inspect_mock.return_value = self.state
        route.return_value = {"dev": "rndis0"}
        result = helper(self.config, "prepare")
        self.assertEqual(result["mutations"], 0)
        self.assertTrue((self.root / "network-state.json").exists())

    @patch("aoc_jetson.network.os.geteuid", return_value=0)
    @patch("aoc_jetson.network.inspect")
    @patch("aoc_jetson.network.route_to")
    def test_prepare_rejects_wrong_data_path(self, route, inspect_mock, _euid):
        inspect_mock.return_value = self.state
        route.return_value = {"dev": "wifi0"}
        with self.assertRaisesRegex(ValueError, "not bound"):
            helper(self.config, "prepare")

    @patch("aoc_jetson.network.run")
    def test_uncommissioned_helper_does_not_run_commands(self, run_mock):
        with self.assertRaisesRegex(ValueError, "Commissioning"):
            helper({**self.config, "commissioned": False}, "prepare")
        run_mock.assert_not_called()

    def test_subprocess_failure_preserves_reviewed_error(self):
        completed = subprocess.CompletedProcess([], 1, json.dumps({"ok": False,
            "error": {"type": "ValueError", "message": "management route changed"}}), "")
        with patch("aoc_jetson.network.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "management route changed"):
                Network(self.config, "config").action("prepare")

    @patch("aoc_jetson.network.run")
    def test_helper_uses_fixed_isolated_entrypoint(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess([], 0,
            json.dumps({"ok": True, "result": {"prepared": True}}), "")
        Network(self.config, "config").action("prepare")
        argv = run_mock.call_args.args[0]
        self.assertEqual(argv[1:3], ["-I", HELPER_ENTRY])
        self.assertNotIn("-m", argv)


if __name__ == "__main__":
    unittest.main()
