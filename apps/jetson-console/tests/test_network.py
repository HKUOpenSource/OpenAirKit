import copy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aoc_jetson.config import DEVICE, REFERENCE, SELECTION, DIAGNOSTICS, RECOVERY, migrate, validate
from aoc_jetson.network import HELPER_ENTRY, Network, align_cellular_mtu, helper, inspect_management, managed_routes, managed_defaults


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
        with patch("aoc_jetson.network.route_rows", return_value=[{"dev": "rndis0", "protocol": "static"}]):
            result = managed_routes(self.config, "prepare")
        self.assertEqual(result["mutations"], 0)
        self.assertFalse((self.root / "network-state.json").exists())

    @patch("aoc_jetson.network.os.geteuid", return_value=0)
    @patch("aoc_jetson.network.inspect")
    @patch("aoc_jetson.network.route_to")
    def test_prepare_rejects_wrong_data_path(self, route, inspect_mock, _euid):
        inspect_mock.return_value = self.state
        route.return_value = {"dev": "wifi0"}
        with self.assertRaisesRegex(ValueError, "gateway"):
            managed_routes(self.config, "prepare")

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
            self.assertEqual(managed_routes(self.config, 'prepare')['mutations'], 2)
            self.assertEqual(managed_routes(self.config, 'prepare')['mutations'], 0)
            with patch('aoc_jetson.network.inspect', side_effect=ValueError('Modem absent')):
                managed_routes(self.config, 'restore')
                managed_routes(self.config, 'restore')
        self.assertEqual(rows, {'10.0.0.1/32': existing})
        self.assertEqual(len(commands), 4)

    def test_conflict_is_found_before_any_route_is_added(self):
        rows = {'172.28.81.15/32': {'dev': 'wifi0', 'protocol': 'static'}}
        with self.kernel(rows) as commands, self.assertRaisesRegex(ValueError, 'Conflicting'):
            managed_routes(self.config, 'prepare')
        self.assertEqual(commands, [])

    def test_changed_route_is_never_deleted(self):
        rows = {}
        with self.kernel(rows) as commands:
            managed_routes(self.config, 'prepare')
            rows['172.28.81.15/32']['gateway'] = '192.168.225.2'
            before = list(commands)
            with self.assertRaisesRegex(ValueError, 'owned route changed'):
                managed_routes(self.config, 'restore')
            self.assertEqual(commands, before)
        self.assertTrue((self.root / 'network-state.json').exists())

    def test_timeout_does_not_claim_or_delete_an_uncertain_route(self):
        rows = {}
        with self.kernel(rows, TimeoutError('Uncertain command outcome')):
            with self.assertRaises(TimeoutError):
                managed_routes(self.config, 'prepare')
            with self.assertRaisesRegex(ValueError, 'uncertain outcome'):
                managed_routes(self.config, 'restore')
        self.assertEqual(len(rows), 1)

    def test_routes_removed_by_kernel_allow_offline_cleanup(self):
        rows = {}
        with self.kernel(rows):
            managed_routes(self.config, 'prepare')
            rows.clear()
            managed_routes(self.config, 'restore')
        self.assertFalse((self.root / 'network-state.json').exists())

    def test_tunnel_route_alone_does_not_prove_management_protection(self):
        with patch('aoc_jetson.network.global_addresses', return_value=['192.0.2.2']), \
                patch('aoc_jetson.network.route_to', return_value={'dev': 'tailscale0'}), \
                patch('aoc_jetson.network.ip_json', return_value=[
                    {'dev': 'rndis0', 'metric': 100}, {'dev': 'wifi0', 'metric': 600}]):
            with self.assertRaisesRegex(ValueError, 'Wi-Fi fallback gateway'):
                inspect_management(self.config)

    def test_cellular_default_still_allows_wifi_fallback_guard(self):
        with patch('aoc_jetson.network.global_addresses', return_value=['192.0.2.2']), \
                patch('aoc_jetson.network.route_to', return_value={'dev': 'tailscale0'}), \
                patch('aoc_jetson.network.ip_json', return_value=[
                    {'dev': 'rndis0', 'metric': 100, 'gateway': '192.168.225.1'},
                    {'dev': 'wifi0', 'metric': 30000, 'gateway': '192.0.2.1'}]):
            self.assertEqual(inspect_management(self.config)['wifi_gateway'], '192.0.2.1')

    def test_probe_routes_are_installed_even_when_default_is_cellular(self):
        rows = {}
        with self.kernel(rows), patch('aoc_jetson.network.route_to', return_value={'dev': 'rndis0'}):
            self.assertEqual(managed_routes(self.config, 'prepare')['mutations'], 3)
        self.assertEqual(len(rows), 3)

    def test_usb_reenumeration_rebuilds_owned_probe_routes(self):
        rows = {}
        with self.kernel(rows):
            managed_routes(self.config, 'prepare')
            self.state['data_interface'] = 'rndis1'
            with patch('aoc_jetson.network.route_to', return_value={'dev': 'rndis1'}):
                managed_routes(self.config, 'prepare')
        self.assertTrue(all(row['dev'] == 'rndis1' for row in rows.values()))
        records = json.loads((self.root / 'network-state.json').read_text())['routes']
        self.assertTrue(all(row['interface'] == 'rndis1' for row in records))

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

    def test_align_cellular_mtu_caps_oversized_interface_and_skips_lower_mtu(self):
        with patch("aoc_jetson.network.Path.read_text", return_value="1500\n"), \
                patch("aoc_jetson.network.run") as run_mock:
            self.assertTrue(align_cellular_mtu("rndis0"))
        run_mock.assert_called_once_with(["ip", "link", "set", "dev", "rndis0", "mtu", "1440"])

        for existing in ("1440\n", "1400\n"):
            with self.subTest(existing=existing.strip()), \
                    patch("aoc_jetson.network.Path.read_text", return_value=existing), \
                    patch("aoc_jetson.network.run") as run_mock:
                self.assertFalse(align_cellular_mtu("rndis0"))
                run_mock.assert_not_called()

    def test_prepare_aligns_cellular_mtu(self):
        rows = {}
        with self.kernel(rows), patch("aoc_jetson.network.align_cellular_mtu") as align_mock:
            managed_routes(self.config, "prepare")
        align_mock.assert_called_once_with("rndis0")


class DefaultRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = configuration(self.root)
        self.state = {'wifi_interface': 'wifi0', 'wifi_gateway': '192.0.2.1',
                      'data_interface': 'rndis0', 'data_address': '192.168.225.29'}
        self.original = [
            {'dst': 'default', 'dev': 'wifi0', 'gateway': '192.0.2.1', 'metric': 30000, 'protocol': 'dhcp'},
            {'dst': 'default', 'dev': 'rndis0', 'gateway': '192.168.225.1', 'metric': 100, 'protocol': 'dhcp'}]
        self.rows = copy.deepcopy(self.original)
        self.commands = []
        self.failure = None
        for name, kw in [('inspect_management', {'return_value': self.state}),
                         ('inspect', {'return_value': self.state}),
                         ('ip_json', {'side_effect': lambda *args: copy.deepcopy(self.rows)}),
                         ('route_to', {'side_effect': self.lookup}),
                         ('run', {'side_effect': self.execute})]:
            patcher = patch('aoc_jetson.network.' + name, **kw)
            patcher.start()
            self.addCleanup(patcher.stop)

    def lookup(self, address, source=None):
        if address == self.config['diagnostics']['rndis_gateway']:
            return {'dev': self.state['data_interface']}
        return min(self.rows, key=lambda row: row.get('metric', 0))

    def execute(self, argv):
        self.commands.append(argv)
        row = {'dst': 'default', 'gateway': argv[6], 'dev': argv[8],
               'metric': int(argv[10]), 'protocol': argv[12]}
        if argv[3] == 'add':
            if isinstance(self.failure, RuntimeError):
                raise self.failure
            self.rows.append(row)
            if self.failure:
                raise self.failure
        else:
            self.rows.remove(row)
        return ''

    def action(self, action):
        return managed_defaults(self.config, action)

    def test_failover_failback_is_idempotent_and_restore_preserves_system_defaults(self):
        self.assertEqual(self.action('fallback')['ipv4_egress'], 'wifi0')
        self.assertEqual(self.action('fallback')['mutations'], 0)
        self.assertEqual(self.action('promote')['ipv4_egress'], 'rndis0')
        self.assertEqual(self.action('promote')['mutations'], 0)
        self.assertEqual(self.action('fallback')['ipv4_egress'], 'wifi0')
        with patch('aoc_jetson.network.inspect_management', side_effect=ValueError('offline')):
            self.action('restore')
            self.action('restore')
        self.assertEqual(self.rows, self.original)
        self.assertFalse((self.root / 'egress-state.json').exists())

    def test_foreign_reserved_or_higher_priority_default_is_never_changed(self):
        for metric in (0, 5, 10):
            with self.subTest(metric=metric):
                self.rows = copy.deepcopy(self.original) + [
                    {'dst': 'default', 'dev': 'eth0', 'gateway': '192.0.2.3', 'metric': metric}]
                before = copy.deepcopy(self.rows)
                with self.assertRaises(ValueError):
                    self.action('fallback')
                self.assertEqual(self.rows, before)
                self.assertFalse(self.commands)

    def test_modified_owned_default_blocks_cleanup(self):
        self.action('promote')
        self.rows[-1]['gateway'] = '192.168.225.2'
        before = list(self.commands)
        with self.assertRaisesRegex(ValueError, 'owned default route changed'):
            self.action('restore')
        self.assertEqual(self.commands, before)

    def test_timeout_keeps_uncertain_ownership_and_rejection_does_not_claim(self):
        self.failure = RuntimeError('File exists')
        with self.assertRaises(RuntimeError):
            self.action('fallback')
        self.assertEqual(json.loads((self.root / 'egress-state.json').read_text())['routes'], [])
        self.failure = TimeoutError('Unknown outcome')
        with self.assertRaises(TimeoutError):
            self.action('fallback')
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            self.action('restore')
        self.assertEqual(len(self.rows), 3)

    def test_fallback_does_not_require_modem_and_reconnect_accepts_new_interface(self):
        self.action('promote')
        # Kernel removes interface-owned routes on USB disappearance.
        self.rows = [row for row in self.rows if row['dev'] != 'rndis0']
        with patch('aoc_jetson.network.inspect', side_effect=ValueError('No modem')):
            self.assertEqual(self.action('fallback')['ipv4_egress'], 'wifi0')
        self.state['data_interface'] = 'rndis1'
        self.assertEqual(self.action('promote')['ipv4_egress'], 'rndis1')
        self.action('restore')
        self.assertEqual(self.rows, [self.original[0]])

    def test_changed_interface_uses_wifi_during_default_replacement(self):
        self.action('promote')
        self.state['data_interface'] = 'rndis1'
        self.commands.clear()
        self.action('promote')
        self.assertEqual([(c[3], c[8]) for c in self.commands],
                         [('add', 'wifi0'), ('del', 'rndis0'), ('add', 'rndis1'), ('del', 'wifi0')])

    def test_ordinary_egress_is_checked_without_a_bound_probe_source(self):
        with patch('aoc_jetson.network.route_to', side_effect=self.lookup) as lookup:
            self.action('promote')
        self.assertIn(unittest.mock.call('1.1.1.1'), lookup.call_args_list)

    def test_helper_restores_both_journals_and_prepare_initializes_fallback(self):
        with patch('aoc_jetson.network.os.geteuid', return_value=0), \
                patch('aoc_jetson.network.managed_routes', return_value={'prepared': True}) as routes:
            helper(self.config, 'prepare')
            self.assertEqual(self.lookup('1.1.1.1')['dev'], 'wifi0')
            helper(self.config, 'promote')
            helper(self.config, 'prepare')
            self.assertEqual(self.lookup('1.1.1.1')['dev'], 'rndis0')
            helper(self.config, 'restore')
            routes.assert_called_with(self.config, 'restore')
        self.assertEqual(self.rows, self.original)


if __name__ == "__main__":
    unittest.main()
