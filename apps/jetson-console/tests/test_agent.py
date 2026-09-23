import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from aoc_jetson.agent import Agent, Conflict, fresh
from aoc_jetson.config import validate
from aoc_jetson.simulator import SimModem, SimNetwork


ROOT = Path(__file__).resolve().parents[3]


def fixture(directory):
    value = json.loads((ROOT / "config" / "jetson.example.json").read_text())
    value.update(state_dir=str(Path(directory) / "state"),
                 web_state_dir=str(Path(directory) / "web"),
                 agent_socket=str(Path(directory) / "device.sock"),
                 commissioned=True, management_verified=True,
                 sim_sha256="0" * 64, simulation=True)
    return validate(value)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.config = fixture(self.temporary.name)
        self.modem = SimModem()
        self.network = SimNetwork()
        self.agent = Agent(self.config, Path(self.temporary.name) / "config.json",
                           self.modem, self.network)
        self.agent.set_maintenance(False)

    def tearDown(self):
        self.temporary.cleanup()

    def wait(self, job):
        self.agent.launch(job["id"], True)
        self.agent.worker.join(3)
        self.assertFalse(self.agent.worker.is_alive())
        return self.agent.store.get_job(job["id"])

    def test_connected_requires_every_base_station_layer_but_not_public_internet(self):
        value = self.agent.sample(True)
        self.assertTrue(value["connected"])
        self.network.failure = "probe"
        value = self.agent.sample(True)
        self.assertFalse(value["connected"])
        self.assertEqual(value["health"], "failed")
        self.network.failure = None
        self.agent.sample(True)
        self.agent.probes["public"] = {"at": time.time(), "kind": "public", "state": "failed"}
        value = self.agent.sample(False)
        self.assertTrue(value["connected"])

    def test_stale_evidence_cannot_remain_connected(self):
        value = self.agent.sample(True)
        value["evidence_at"] = time.time() - 30
        value = fresh(value)
        self.assertFalse(value["connected"])
        self.assertEqual(value["quality"], "stale")
        self.assertTrue(all(layer["state"] == "unknown" for layer in value["layers"]))

    def test_setup_is_single_stack_data_only_and_preserves_residual_contexts(self):
        job = self.agent.create("setup", self.config["revision"])
        result = self.wait(job)
        self.assertEqual(result["state"], "complete")
        self.assertFalse(any("IMS" in step["id"] for step in result["steps"]))
        self.assertEqual(self.modem.contexts[2]["dnn"], "ims")
        self.assertFalse(any(call[1] == 2 for call in self.modem.calls))
        self.assertFalse(any(call[0] in {"nr5g", "sa", "band78", "automatic"}
                             for call in self.modem.calls))
        self.assertEqual(result["result"]["radio_configuration"]["state"], "preserved")
        self.assertEqual(result["result"]["radio_configuration"]["mutations"], 0)
        self.assertTrue(self.agent.status()["connected"])

    def test_speed_is_rejected_at_create_launch_and_execution(self):
        with self.assertRaises(ValueError):
            self.agent.create("speed", self.config["revision"])
        job = self.agent.store.new_job("speed", self.config["revision"], ["Download"], {})
        self.agent.current = job["id"]
        with self.assertRaises(ValueError):
            self.agent.launch(job["id"], True)
        self.agent.execute(job)
        self.assertEqual(self.agent.store.get_job(job["id"])["state"], "failed")
        self.assertFalse(hasattr(self.network, "speed"))

    def test_registration_independent_of_management_policy_and_diagnostics(self):
        self.config["selection"]["pci"] = 123
        self.network.failure = "probe"
        with patch.object(self.network, "snapshot", return_value={**self.network.snapshot(), "management_protected": False}):
            value = self.agent.sample(True)
        self.assertTrue(value["registered"])
        self.assertTrue(value["data_session_active"])
        self.assertFalse(value["connected"])
        self.assertFalse(value["lab_policy_match"])
        self.assertFalse(value["management_protected"])

    def test_registration_transition_invalidates_old_probes(self):
        self.assertTrue(self.agent.sample(True)["connected"])
        self.modem.registered = False
        self.agent.sample(False)
        self.modem.registered = True
        self.assertFalse(self.agent.sample(False)["connected"])
        self.assertTrue(self.agent.sample(True)["connected"])

    def test_auto_recovery_waits_then_reconnects_once_with_a_budget(self):
        self.agent.store.set("recovery_paused", False)
        self.modem.registered = False
        self.agent.sample(True)
        self.agent.auto_reconcile()
        self.assertIsNone(self.agent.current)
        self.agent.outage_since = time.time() - 121
        self.agent.auto_reconcile()
        self.agent.worker.join(3)
        self.assertTrue(self.agent.sample(True)["connected"])
        self.assertEqual(sum(call[0] == "cfun0" for call in self.modem.calls), 1)
        self.assertEqual(self.agent.store.setting("auto_attempts"), 1)
        self.agent.store.set("auto_attempts", 2)
        self.agent.store.set("last_auto_attempt", 0)
        self.modem.registered = False
        self.agent.sample(True)
        self.agent.outage_since = time.time() - 121
        self.agent.auto_reconcile()
        self.assertTrue(self.agent.store.setting("recovery_paused"))

    def test_probe_failure_does_not_trigger_automatic_reset(self):
        self.agent.store.set("recovery_paused", False)
        self.network.failure = "probe"
        self.agent.sample(True)
        self.agent.outage_since = time.time() - 1000
        self.agent.auto_reconcile()
        self.assertFalse(self.modem.calls)

    def test_manual_setup_advances_one_persisted_step_at_a_time(self):
        job = self.agent.create("setup", self.config["revision"], {"mode": "manual"})
        first = self.wait(job)
        self.assertEqual(first["state"], "paused")
        self.assertEqual(sum(step["state"] == "complete" for step in first["steps"]), 1)
        second = self.wait(first)
        self.assertEqual(second["state"], "paused")
        self.assertEqual(sum(step["state"] == "complete" for step in second["steps"]), 2)

    def test_cancelled_recovery_clears_task_signal_and_sampling_recovers(self):
        job = self.agent.create("recover", self.config["revision"])
        self.agent.cancel.set()
        self.agent.execute(job)
        self.assertEqual(self.agent.store.get_job(job["id"])["state"], "cancelled")
        self.assertFalse(self.agent.cancel.is_set())
        self.assertEqual(self.agent.sample(True)["quality"], "ok")

    def test_recovery_records_failed_precheck_before_bounded_repair(self):
        self.network.failure = "probe"
        job = self.agent.create("recover", self.config["revision"])
        result = self.wait(job)
        self.assertFalse(result["result"]["initial_verification"]["connected"])
        self.assertIn("prepare", self.network.calls)
        self.assertLessEqual(sum(call[0] == "cfun0" for call in self.modem.calls), 1)
        self.assertEqual(result["state"], "failed")

    def test_revision_conflict_maintenance_and_concurrency(self):
        with self.assertRaises(Conflict):
            self.agent.create("setup", "old")
        self.agent.set_maintenance(True)
        with self.assertRaises(Conflict):
            self.agent.create("setup", self.config["revision"])
        self.agent.set_maintenance(False)
        first = self.agent.create("setup", self.config["revision"])
        with self.assertRaises(Conflict):
            self.agent.create("recover", self.config["revision"])
        self.agent.cancel_job(first["id"])

    def test_process_restart_interrupts_unfinished_job(self):
        job = self.agent.create("setup", self.config["revision"])
        other = Agent(self.config, Path(self.temporary.name) / "config.json",
                      SimModem(), SimNetwork())
        self.assertTrue(other.interrupted)
        self.assertEqual(other.store.get_job(job["id"])["state"], "interrupted")
        self.assertTrue(other.store.setting("recovery_paused"))


if __name__ == "__main__":
    unittest.main()
