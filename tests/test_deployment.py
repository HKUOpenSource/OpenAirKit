import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.aoclib.core import compose_config, nf_config, prepare, schema_only
from scripts.aoclib.preflight import inspect
from scripts.aoclib.cli import compose_args, core_up, initialize_empty_schema


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/spark.example.json").read_text())
        self.images = json.loads((ROOT / "config/images.lock.json").read_text())

    def bundle(self, temporary):
        root = Path(temporary)
        schema = root / "input.sql"
        schema.write_text("CREATE TABLE `AuthenticationSubscription` (x INT);")
        bundle = root / "bundle"
        prepare(self.config, self.images, bundle, schema)
        return bundle

    def test_core_isolated_and_all_images_pinned(self):
        compose = compose_config(self.config, self.images)
        self.assertEqual(len(compose["services"]), 10)
        for service in compose["services"].values():
            for forbidden in ("container_name", "ports", "network_mode", "privileged"):
                self.assertNotIn(forbidden, service)
            self.assertIn("@sha256:", service["image"])
        self.assertEqual(compose["networks"]["core"]["name"], "aoc-cn5g-net")

    def test_rejects_mutable_image_reference(self):
        self.images["ims"]["reference"] = "oaisoftwarealliance/ims:latest"
        with self.assertRaises(ValueError):
            compose_config(self.config, self.images)

    def test_data_and_ims_have_distinct_qos_and_pools(self):
        config = nf_config(self.config, "not-a-real-secret")
        qos = {item["dnn"]: item["qos_profile"]["5qi"] for item in config["smf"]["local_subscription_infos"]}
        self.assertEqual(qos, {"oai": 9, "ims": 5})
        self.assertEqual(config["smf"]["ims"]["pcscf_ipv4"], "172.28.80.19")
        self.assertEqual({item["ipv4_subnet"] for item in config["dnns"]}, {"10.80.0.0/24", "10.80.9.0/24"})

    def test_schema_omits_sample_subscribers(self):
        sql = "CREATE TABLE `AuthenticationSubscription` (x INT); INSERT INTO `AuthenticationSubscription` VALUES (123); ALTER TABLE `AuthenticationSubscription` ADD PRIMARY KEY(x);"
        result = schema_only(sql)
        self.assertNotIn("INSERT", result)
        self.assertNotIn("123", result)
        self.assertIn("ADD PRIMARY KEY", result)

    def test_prepare_is_private_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "schema.sql"
            source.write_text("CREATE TABLE `AuthenticationSubscription` (x INT);")
            bundle = root / "bundle"
            prepare(self.config, self.images, bundle, source)
            password = bundle / "secrets/db_password"
            original = password.read_bytes()
            self.assertEqual(password.stat().st_mode & 0o777, 0o600)
            self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
            self.assertFalse(json.loads((bundle / "bundle.json").read_text())["subscribers_provisioned"])
            with self.assertRaises(ValueError):
                prepare(self.config, self.images, bundle, source)
            self.assertEqual(password.read_bytes(), original)

    @patch("scripts.aoclib.cli.subprocess.run")
    @patch("scripts.aoclib.cli.subprocess.check_output", return_value="")
    def test_core_failure_cleanup_targets_only_new_project(self, output, run):
        run.side_effect = [subprocess.CalledProcessError(1, "up"), subprocess.CompletedProcess([], 0)]
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(temporary)
            with self.assertRaises(subprocess.CalledProcessError):
                core_up(self.config, bundle)
        cleanup = run.call_args_list[-1].args[0]
        self.assertIn("aoc-cn5g", cleanup)
        self.assertIn("stop", cleanup)
        self.assertNotIn("down", cleanup)
        self.assertNotIn("oai-gnb.service", cleanup)

    @patch("scripts.aoclib.cli.subprocess.run")
    @patch("scripts.aoclib.cli.subprocess.check_output", return_value='{"Service":"mysql","State":"running","Health":"healthy"}')
    def test_existing_core_is_not_stopped_on_repeated_up(self, output, run):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(temporary)
            with self.assertRaises(ValueError):
                core_up(self.config, bundle)
        run.assert_not_called()

    @patch("scripts.aoclib.cli.subprocess.run")
    @patch("scripts.aoclib.cli.subprocess.check_output")
    def test_healthy_core_start_is_idempotent(self, output, run):
        output.return_value = json.dumps([{"Service": name, "State": "running", "Health": "healthy"}
                                          for name in self.images])
        with tempfile.TemporaryDirectory() as temporary:
            core_up(self.config, self.bundle(temporary))
        run.assert_not_called()

    def test_rejects_compose_with_foreign_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(temporary)
            path = bundle / "compose.json"
            content = json.loads(path.read_text())
            content["services"]["mysql"]["volumes"].append("/old/database:/foreign")
            path.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "Compose differs"):
                compose_args(self.config, bundle)

    def test_rejects_bundle_for_different_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(temporary)
            self.config["radio"]["tac"] = 2
            with self.assertRaisesRegex(ValueError, "configuration differs"):
                compose_args(self.config, bundle)

    def test_rejects_nf_configuration_pointing_at_old_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(temporary)
            path = bundle / "nf.json"
            content = json.loads(path.read_text())
            content["database"]["host"] = "192.168.70.131"
            path.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "NF configuration differs"):
                compose_args(self.config, bundle)

    @patch("scripts.aoclib.cli.subprocess.run")
    @patch("scripts.aoclib.cli.subprocess.check_output", return_value="1\n")
    def test_schema_recovery_refuses_nonempty_database(self, output, run):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "empty database"):
                initialize_empty_schema(self.config, self.bundle(temporary))
        run.assert_not_called()

    @patch("scripts.aoclib.cli.subprocess.run")
    @patch("scripts.aoclib.cli.subprocess.check_output", return_value="0\n")
    def test_schema_recovery_uses_stdin_and_own_database(self, output, run):
        with tempfile.TemporaryDirectory() as temporary:
            initialize_empty_schema(self.config, self.bundle(temporary))
        argv = run.call_args.args[0]
        self.assertIn("aoc-cn5g", argv)
        self.assertIn("AuthenticationSubscription", run.call_args.kwargs["input"])
        self.assertNotIn("INSERT", run.call_args.kwargs["input"])


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
