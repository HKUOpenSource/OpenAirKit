import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aoc_jetson.config import DEVICE, REFERENCE, SELECTION, DIAGNOSTICS, RECOVERY, migrate, public, validate
from aoc_jetson.store import Store


def configuration(root):
    return {"schema_version": 3, "name": "agentic-ocudu-jetson-v2",
            "selection": copy.deepcopy(SELECTION), "diagnostics": copy.deepcopy(DIAGNOSTICS),
            "recovery": copy.deepcopy(RECOVERY), "network": copy.deepcopy(REFERENCE), "device": copy.deepcopy(DEVICE),
            "management": {"wifi_interface": "auto", "tailscale_interface": "tailscale0",
                           "spark_address": "192.0.2.20"},
            "state_dir": str(root / "state"), "web_state_dir": str(root / "web"),
            "agent_socket": str(root / "run/device.sock"),
            "commissioned": False, "management_verified": False}


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_single_data_contract_has_no_environment_or_ims(self):
        config = validate(configuration(self.root))
        exposed = public(config)
        self.assertEqual(exposed["network"]["data"]["dnn"], "oai")
        self.assertNotIn("profiles", json.dumps(exposed))
        self.assertNotIn("ims", json.dumps(exposed).lower())
        self.assertNotIn("sim_sha256", exposed)

    def test_access_and_policy_are_field_validated(self):
        candidate = configuration(self.root)
        candidate["network"]["data"]["ue_pool"] = "10.80.0.0/24"
        candidate["selection"]["pci"] = 10
        self.assertEqual(validate(candidate)["selection"]["pci"], 10)
        candidate["selection"]["pci"] = 1008
        with self.assertRaises(ValueError):
            validate(candidate)

    def test_schema_two_migration_preserves_radio_and_removes_benchmark_port(self):
        old = configuration(self.root)
        old["schema_version"] = 2
        old["network"].update(tac=1, radio={"pci": 666, "band": 78, "carrier_arfcn": 643392},
                              user_plane={"iperf_port": 5201})
        updated = validate(migrate(old))
        self.assertEqual(updated["selection"]["pci"], 666)
        self.assertIsNone(updated["selection"]["ssb_arfcn"])
        self.assertNotIn("iperf_port", updated["diagnostics"])
        self.assertEqual(old["schema_version"], 2)

    def test_upgrade_preserves_history_and_retires_pending_speed_jobs(self):
        path = self.root / "existing.db"
        store = Store(path)
        job = store.new_job("speed", "old", ["Download"], {})
        with store.connect() as db:
            db.execute("PRAGMA user_version=1")
        updated = Store(path)
        self.assertTrue(updated.get_job(job["id"])["retired"])
        self.assertEqual(updated.get_job(job["id"])["state"], "interrupted")
        self.assertEqual(len(list(self.root.glob("existing.db.before-schema-2-*"))), 1)

    def test_store_has_no_environment_columns_and_interrupts_jobs(self):
        store = Store(self.root / "device.db")
        job = store.new_job("setup", "revision", ["Inspect device"], {})
        self.assertEqual(store.get_job(job["id"])["state"], "ready")
        self.assertTrue(store.interrupt())
        self.assertEqual(store.get_job(job["id"])["state"], "interrupted")
        with sqlite3.connect(store.path) as db:
            event_columns = [row[1] for row in db.execute("PRAGMA table_info(events)")]
            metric_columns = [row[1] for row in db.execute("PRAGMA table_info(metrics)")]
        self.assertNotIn("profile", event_columns + metric_columns)

    def test_store_backs_up_unversioned_database(self):
        path = self.root / "existing.db"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE old(value TEXT)")
        Store(path)
        self.assertEqual(len(list(self.root.glob("existing.db.before-schema-2-*"))), 1)


if __name__ == "__main__":
    unittest.main()
