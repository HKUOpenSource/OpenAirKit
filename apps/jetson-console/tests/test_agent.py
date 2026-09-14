import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

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

    def test_speed_keeps_direction_results_separate(self):
        job = self.agent.create("speed", self.config["revision"],
                                {"direction": "both", "duration": 5, "parallel": 1})
        result = self.wait(job)
        self.assertEqual(result["state"], "complete")
        self.assertTrue(result["result"]["bidirectional_passed"])
        self.assertEqual(result["result"]["download"]["bps"], 38e6)
        self.assertEqual(result["result"]["upload"]["bps"], 8e6)

    def test_manual_setup_advances_one_persisted_step_at_a_time(self):
        job = self.agent.create("setup", self.config["revision"], {"mode": "manual"})
        first = self.wait(job)
        self.assertEqual(first["state"], "paused")
        self.assertEqual(sum(step["state"] == "complete" for step in first["steps"]), 1)
        second = self.wait(first)
        self.assertEqual(second["state"], "paused")
        self.assertEqual(sum(step["state"] == "complete" for step in second["steps"]), 2)

    def test_failed_direction_does_not_claim_combined_success(self):
        self.network.failure = "upload"
        job = self.agent.create("speed", self.config["revision"],
                                {"direction": "both", "duration": 5, "parallel": 1})
        result = self.wait(job)
        self.assertEqual(result["state"], "failed")
        self.assertIn("download", result["result"])
        self.assertNotIn("bidirectional_passed", result["result"])

    def test_cancelled_speed_clears_task_signal_and_sampling_recovers(self):
        job = self.agent.create("speed", self.config["revision"],
                                {"direction": "both", "duration": 30, "parallel": 4})
        self.agent.launch(job["id"], True)
        deadline = time.monotonic() + 1
        while self.agent.store.get_job(job["id"])["state"] == "ready" and time.monotonic() < deadline:
            time.sleep(.005)
        self.agent.cancel_job(job["id"])
        self.agent.worker.join(3)
        result = self.agent.store.get_job(job["id"])
        self.assertEqual(result["state"], "cancelled")
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
