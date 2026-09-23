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
