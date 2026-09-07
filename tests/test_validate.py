import copy
import json
from pathlib import Path
import unittest

from scripts.validate import validate


ROOT = Path(__file__).resolve().parents[1]


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/spark.example.json").read_text())

    def assert_error(self, text):
        self.assertTrue(any(text in error for error in validate(self.config)),
                        validate(self.config))

    def test_candidate_plan_allows_standard_ports_on_distinct_addresses(self):
        self.assertEqual(validate(self.config), [])

    def test_rejects_core_overlap_with_stopped_legacy_network(self):
        self.config["network"]["subnet"] = "192.168.72.128/26"
        self.assert_error("overlaps")

    def test_rejects_ue_pool_overlap_with_existing_ue_routes(self):
        self.config["network"]["ue_pools"]["oai"] = "10.0.2.0/24"
        self.assert_error("overlaps")

    def test_rejects_overlapping_new_pools(self):
        self.config["network"]["ue_pools"]["ims_reserved"] = "10.80.0.128/25"
        self.assert_error("overlaps")

    def test_rejects_reserved_monitor_port(self):
        self.config["listeners"][4]["port"] = 8787
        self.assert_error("reserved tcp port")

    def test_rejects_wildcard_gtpu(self):
        self.config["listeners"][1]["address"] = "0.0.0.0"
        self.assert_error("wildcard")
        self.assert_error("conflicts with legacy_gnb_n3")

    def test_rejects_existing_dual_stack_wildcard(self):
        self.config["legacy"]["listeners"].append({
            "name": "other_app", "protocol": "tcp", "address": "::", "port": 8877})
        self.assert_error("conflicts with other_app")

    def test_rejects_duplicate_socket(self):
        duplicate = copy.deepcopy(self.config["listeners"][4])
        duplicate["name"] = "another_web"
        self.config["listeners"].append(duplicate)
        self.assert_error("conflicts with monitor_web")

    def test_rejects_control_exposure(self):
        self.config["listeners"][5]["address"] = "172.28.80.1"
        self.assert_error("loopback TCP")

    def test_rejects_legacy_data_path(self):
        self.config["paths"]["state"] = "/var/lib/oai-spark-platform"
        self.assert_error("must stay under")

    def test_rejects_path_traversal(self):
        self.config["paths"]["state"] = "/var/lib/agentic-ocudu/../oai-spark-platform"
        self.assert_error("must stay under")

    def test_rejects_network_or_duplicate_nf_addresses(self):
        self.config["network"]["addresses"]["amf"] = "172.28.80.0"
        self.assert_error("not a usable core address")
        self.config["network"]["addresses"]["amf"] = "172.28.80.13"
        self.assert_error("Duplicate core address")

    def test_rejects_long_bridge_name(self):
        self.config["names"]["bridge"] = "aoc-bridge-name-too-long"
        self.assert_error("exceeds 15 bytes")

    def test_rejects_changed_legacy_unit_contract(self):
        self.config["legacy"]["radio_unit"] = "different-gnb.service"
        self.assert_error("switching contract")

    def test_reports_malformed_config(self):
        self.assertTrue(validate({}))


if __name__ == "__main__":
    unittest.main()
