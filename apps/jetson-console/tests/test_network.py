import copy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aoc_jetson.config import DEVICE, REFERENCE, SELECTION, DIAGNOSTICS, RECOVERY, migrate, validate
from aoc_jetson.network import HELPER_ENTRY, Network, helper, inspect_management


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

    def snapshot(self, network, tick, counters, interface="rndis0", ifindex=7,
                 error=None, wall_time=None):
        indices = iter(ifindex if isinstance(ifindex, tuple) else (ifindex, ifindex))

        def read(path):
            if path.name == "ifindex":
                return str(next(indices))
            if error and path.name == "rx_bytes":
                raise error
            return str({"rx_bytes": counters[0], "tx_bytes": counters[1]}[path.name])

        with patch("aoc_jetson.network.inspect", return_value={**self.state, "data_interface": interface}), \
                patch("aoc_jetson.network.inspect_management", return_value={"management_protected": True}), \
                patch("aoc_jetson.network.route_to", return_value={"dev": interface}), \
                patch("aoc_jetson.network.Path.read_text", autospec=True, side_effect=read), \
                patch("aoc_jetson.network.time.time", return_value=tick if wall_time is None else wall_time), \
                patch("aoc_jetson.network.time.monotonic", return_value=tick):
            return network.snapshot()

    def assert_rates(self, value, rx, tx):
        self.assertEqual((value["rx_bps"], value["tx_bps"]), (rx, tx))

    def test_rates_require_two_samples_of_the_same_interface(self):
        network = Network(self.config, "config")
        self.assert_rates(self.snapshot(network, 100, (1000, 2000)), None, None)
        self.assert_rates(self.snapshot(network, 102, (1500, 3000)), 2000, 4000)

    def test_interface_rename_or_replacement_starts_a_new_rate_interval(self):
        for interface, ifindex in (("rndis1", 7), ("rndis0", 8), ("rndis1", 8)):
            with self.subTest(interface=interface, ifindex=ifindex):
                network = Network(self.config, "config")
                self.snapshot(network, 100, (1000, 2000))
                changed = self.snapshot(network, 101, (1000000, 2000000), interface, ifindex)
                self.assertEqual(changed["quality"], "ok")
                self.assert_rates(changed, None, None)
                self.assert_rates(self.snapshot(network, 103, (1000500, 2001000), interface, ifindex),
                                  2000, 4000)

    def test_discovery_failure_clears_rate_baseline(self):
        network = Network(self.config, "config")
        self.snapshot(network, 100, (1000, 2000))
        with patch("aoc_jetson.network.inspect", side_effect=ValueError("Device disappeared")), \
                patch("aoc_jetson.network.inspect_management", return_value={"management_protected": True}):
            unavailable = network.snapshot()
        self.assertEqual(unavailable["quality"], "unavailable")
        self.assert_rates(unavailable, None, None)
        self.assert_rates(self.snapshot(network, 102, (1000000, 2000000)), None, None)
        self.assert_rates(self.snapshot(network, 104, (1000500, 2001000)), 2000, 4000)

    def test_counter_read_failure_clears_rate_baseline(self):
        network = Network(self.config, "config")
        self.snapshot(network, 100, (1000, 2000))
        unavailable = self.snapshot(network, 101, (0, 0), error=FileNotFoundError("Interface disappeared"))
        self.assertEqual(unavailable["quality"], "unavailable")
        self.assert_rates(unavailable, None, None)
        self.assert_rates(self.snapshot(network, 102, (1000000, 2000000)), None, None)

    def test_counter_reset_starts_a_new_rate_interval(self):
        network = Network(self.config, "config")
        self.snapshot(network, 100, (1000, 2000))
        self.assert_rates(self.snapshot(network, 101, (100, 3000)), None, None)
        self.assert_rates(self.snapshot(network, 103, (600, 4000)), 2000, 4000)

    def test_replacement_during_counter_read_discards_sample(self):
        network = Network(self.config, "config")
        self.snapshot(network, 100, (1000, 2000))
        value = self.snapshot(network, 101, (1000000, 2000000), ifindex=(7, 8))
        self.assertEqual(value["quality"], "unavailable")
        self.assert_rates(value, None, None)
        self.assert_rates(self.snapshot(network, 102, (1000000, 2000000), ifindex=8), None, None)
        self.assert_rates(self.snapshot(network, 104, (1000500, 2001000), ifindex=8), 2000, 4000)

    def test_rates_use_elapsed_time_despite_wall_clock_changes(self):
        network = Network(self.config, "config")
        self.snapshot(network, 100, (1000, 2000), wall_time=1000)
        value = self.snapshot(network, 102, (1500, 3000), wall_time=900)
        self.assertEqual(value["at"], 900)
        self.assert_rates(value, 2000, 4000)

    @patch("aoc_jetson.network.os.geteuid", return_value=0)
    @patch("aoc_jetson.network.inspect")
    @patch("aoc_jetson.network.route_to")
    def test_prepare_accepts_existing_bound_routes_without_mutation(self, route, inspect_mock, _euid):
        inspect_mock.return_value = self.state
        route.return_value = {"dev": "rndis0"}
        result = helper(self.config, "prepare")
        self.assertEqual(result["mutations"], 0)
        self.assertFalse((self.root / "network-state.json").exists())

    @patch("aoc_jetson.network.os.geteuid", return_value=0)
    @patch("aoc_jetson.network.inspect")
    @patch("aoc_jetson.network.route_to")
    def test_prepare_rejects_wrong_data_path(self, route, inspect_mock, _euid):
        inspect_mock.return_value = self.state
        route.return_value = {"dev": "wifi0"}
        with self.assertRaisesRegex(ValueError, "gateway"):
            helper(self.config, "prepare")

    @contextmanager
    def kernel(self, rows, fail=None):
        commands = []
        def lookup(address, source=None):
            if address == self.config['diagnostics']['rndis_gateway']:
                return {'dev': 'rndis0'}
            return rows.get(address + '/32', {'dev': 'wifi0'})
        def ip(*args):
            self.assertIn('-N', args)
            return [rows[args[-1]]] if args[-1] in rows else []
        def execute(argv):
            commands.append(argv)
            destination = argv[4]
            if argv[3] == 'add':
                rows[destination] = {'dst': destination.removesuffix('/32'), 'dev': argv[8],
                                     'gateway': argv[6], 'protocol': '186'}
                if fail:
                    raise fail
            else:
                del rows[destination]
            return ''
        with patch('aoc_jetson.network.os.geteuid', return_value=0), \
                patch('aoc_jetson.network.inspect', return_value=self.state), \
                patch('aoc_jetson.network.route_to', side_effect=lookup), \
                patch('aoc_jetson.network.ip_json', side_effect=ip), \
                patch('aoc_jetson.network.run', side_effect=execute):
            yield commands

    def test_independent_start_stop_routes_preserve_existing_routes(self):
        existing = {'dst': '10.0.0.1', 'dev': 'rndis0', 'gateway': '192.168.225.1', 'protocol': 'static'}
        rows = {'10.0.0.1/32': existing}
        with self.kernel(rows) as commands:
            self.assertEqual(helper(self.config, 'prepare')['mutations'], 2)
            self.assertEqual(helper(self.config, 'prepare')['mutations'], 0)
            with patch('aoc_jetson.network.inspect', side_effect=ValueError('Modem absent')):
                helper(self.config, 'restore')
                helper(self.config, 'restore')
        self.assertEqual(rows, {'10.0.0.1/32': existing})
        self.assertEqual(len(commands), 4)

    def test_conflict_is_found_before_any_route_is_added(self):
        rows = {'172.28.81.15/32': {'dev': 'wifi0', 'protocol': 'static'}}
        with self.kernel(rows) as commands, self.assertRaisesRegex(ValueError, 'Conflicting'):
            helper(self.config, 'prepare')
        self.assertEqual(commands, [])

    def test_changed_route_is_never_deleted(self):
        rows = {}
        with self.kernel(rows) as commands:
            helper(self.config, 'prepare')
            rows['172.28.81.15/32']['gateway'] = '192.168.225.2'
            before = list(commands)
            with self.assertRaisesRegex(ValueError, 'owned route changed'):
                helper(self.config, 'restore')
            self.assertEqual(commands, before)
        self.assertTrue((self.root / 'network-state.json').exists())

    def test_timeout_does_not_claim_or_delete_an_uncertain_route(self):
        rows = {}
        with self.kernel(rows, TimeoutError('Uncertain command outcome')):
            with self.assertRaises(TimeoutError):
                helper(self.config, 'prepare')
            with self.assertRaisesRegex(ValueError, 'uncertain outcome'):
                helper(self.config, 'restore')
        self.assertEqual(len(rows), 1)

    def test_routes_removed_by_kernel_allow_offline_cleanup(self):
        rows = {}
        with self.kernel(rows):
            helper(self.config, 'prepare')
            rows.clear()
            helper(self.config, 'restore')
        self.assertFalse((self.root / 'network-state.json').exists())

    def test_tunnel_route_alone_does_not_prove_management_protection(self):
        with patch('aoc_jetson.network.global_addresses', return_value=['192.0.2.2']), \
                patch('aoc_jetson.network.route_to', return_value={'dev': 'tailscale0'}), \
                patch('aoc_jetson.network.ip_json', return_value=[
                    {'dev': 'rndis0', 'metric': 100}, {'dev': 'wifi0', 'metric': 600}]):
            with self.assertRaisesRegex(ValueError, 'preferred IPv4 default'):
                inspect_management(self.config)

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
