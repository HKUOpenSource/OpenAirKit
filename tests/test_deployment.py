import json
from pathlib import Path
import unittest

from scripts.aoclib.preflight import inspect

ROOT = Path(__file__).resolve().parents[1]


class LivePreflightTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/spark.example.json").read_text())
        self.inventory = {"architecture": "aarch64", "routes": {"ok": True, "data": [{"dst": "default"}]},
                          "addresses": {"ok": True, "data": []}, "networks": {"ok": True, "data": []},
                          "listeners": {"ok": True, "data": ""}, "units": {"ok": True, "data": ""}}

    def test_core_preflight_does_not_require_sudo_or_stop_radio(self):
        self.assertEqual(inspect(self.config, self.inventory), [])

    def test_unavailable_inventory_fails_closed(self):
        self.inventory["networks"]["ok"] = False
        self.assertTrue(inspect(self.config, self.inventory))

    def test_stopped_network_still_conflicts(self):
        self.inventory["networks"]["data"] = [{"Name": "unrelated", "IPAM": {"Config": [{"Subnet": "172.28.0.0/16"}]}}]
        self.assertTrue(any("Docker subnet conflict" in error for error in inspect(self.config, self.inventory)))

    def test_owned_network_and_its_host_routes_are_allowed(self):
        self.inventory["networks"]["data"] = [{"Name": "aoc-cn5g-net", "Labels": {"com.docker.compose.project": "aoc-cn5g"},
            "IPAM": {"Config": [{"Subnet": "172.28.80.0/24", "Gateway": "172.28.80.1"}]},
            "Options": {"com.docker.network.bridge.name": "aoc-cn5g"}}]
        self.inventory["routes"]["data"].append({"dst": "172.28.80.1", "dev": "aoc-cn5g"})
        self.assertEqual(inspect(self.config, self.inventory), [])
        self.inventory["networks"]["data"][0]["Labels"] = {}
        self.assertTrue(inspect(self.config, self.inventory))

    def test_wildcard_ipv6_blocks_planned_ipv4_socket(self):
        self.inventory["listeners"]["data"] = "tcp LISTEN 0 128 [::]:8877 [::]:*\n"
        self.assertTrue(any("Listener conflict" in error for error in inspect(self.config, self.inventory)))

    def test_radio_lifecycle_does_not_reserve_the_independent_monitor_port(self):
        self.inventory["listeners"]["data"] = 'tcp LISTEN 0 2048 127.0.0.1:8877 0.0.0.0:*\n'
        self.assertEqual(inspect(self.config, self.inventory, scope="radio"), [])
        self.assertTrue(any("monitor_web" in error for error in inspect(self.config, self.inventory)))

    def test_radio_scope_keeps_control_and_gtpu_conflict_checks(self):
        for listener in ('tcp LISTEN 0 128 [::]:8001 [::]:*',
                         'udp UNCONN 0 0 172.28.80.1:2152 0.0.0.0:*'):
            with self.subTest(listener=listener):
                self.inventory["listeners"]["data"] = listener
                self.assertTrue(any("Listener conflict" in error for error in inspect(self.config, self.inventory, scope="radio")))

    def test_unknown_preflight_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "scope"):
            inspect(self.config, self.inventory, scope="skip-all")

    def test_new_ue_pool_must_not_overlap_live_route(self):
        self.inventory["routes"]["data"].append({"dst": "10.80.0.0/16", "dev": "vpn0"})
        self.assertTrue(any("Host route conflict" in error for error in inspect(self.config, self.inventory)))

    def test_rf_start_rejects_unverified_parameters_and_sudo(self):
        errors = inspect(self.config, self.inventory, radio=True)
        self.assertTrue(any("sudo" in error for error in errors))
        self.assertTrue(any("RF parameters" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
