import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from aoc_jetson.agent import Agent, Conflict, fresh
from aoc_jetson.config import validate
from aoc_jetson.modem import Modem
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

    def test_resume_route_failure_preserves_maintenance_without_modem_writes(self):
        self.agent.set_maintenance(True)
        self.network.failure = 'prepare'
        with patch.object(self.modem, 'write') as write, self.assertRaisesRegex(ValueError, 'route failure'):
            self.agent.set_maintenance(False)
        self.assertTrue(self.agent.maintenance)
        self.assertTrue(self.agent.store.setting('recovery_paused', False))
        write.assert_not_called()

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

    def test_probes_share_a_sampling_window_and_keep_individual_failures(self):
        barrier = threading.Barrier(4, timeout=2)
        probe = self.network.probe

        def simultaneous(kind, cancel=None):
            barrier.wait()
            if kind == "public":
                raise TimeoutError("Public probe timed out")
            return probe(kind, cancel)

        with patch.object(self.network, "probe", side_effect=simultaneous):
            value = self.agent.sample(True)
        self.assertTrue(value["connected"])
        self.assertTrue(all(value["probes"][kind]["state"] == "ok"
                            for kind in ("gateway", "upf", "ext_dn")))
        self.assertEqual(value["probes"]["public"]["state"], "unknown")
        self.assertIn("timed out", self.agent.probes["public"]["reason"])

    def test_parallel_required_probe_failure_still_blocks_connection(self):
        probe = self.network.probe

        def failure(kind, cancel=None):
            if kind == "upf":
                raise TimeoutError("UPF probe timed out")
            return probe(kind, cancel)

        with patch.object(self.network, "probe", side_effect=failure):
            value = self.agent.sample(True)
        self.assertFalse(value["connected"])
        self.assertEqual(value["health"], "unknown")
        self.assertEqual(value["probes"]["upf"]["state"], "unknown")

    def route_sample(self):
        self.agent.sample(True)
        self.agent.reconcile_routes()

    def test_cellular_failback_requires_two_fresh_samples_even_when_recovery_paused(self):
        self.assertTrue(self.agent.store.setting('recovery_paused'))
        self.route_sample()
        self.assertEqual(self.network.mode, 'wifi')
        self.agent.reconcile_routes()  # The same cached evidence is not confirmation.
        self.assertEqual(self.network.mode, 'wifi')
        self.route_sample()
        self.assertEqual(self.network.mode, 'cellular')
        self.assertEqual(self.agent.status()['routing']['mode'], 'cellular')
        self.assertFalse(self.modem.calls)

    def test_public_failure_falls_back_without_reset_and_recovers_automatically(self):
        self.route_sample()
        self.route_sample()
        probe = self.network.probe
        def no_internet(kind, cancel=None):
            return {**probe(kind, cancel), 'state': 'failed' if kind == 'public' else 'ok'}
        with patch.object(self.network, 'probe', side_effect=no_internet):
            self.route_sample()
            self.assertTrue(self.agent.status()['connected'])  # Base station is still connected.
            self.assertEqual(self.network.mode, 'cellular')
            self.route_sample()
            self.assertEqual(self.network.mode, 'wifi')
        self.route_sample()
        self.assertEqual(self.network.mode, 'wifi')
        self.route_sample()
        self.assertEqual(self.network.mode, 'cellular')
        self.assertFalse(self.modem.calls)

    def test_partial_probe_refresh_does_not_confirm_failback(self):
        self.route_sample()
        self.agent.cached['probes']['public']['at'] += .001
        self.agent.reconcile_routes()
        self.assertEqual(self.network.mode, 'wifi')
        self.route_sample()
        self.assertEqual(self.network.mode, 'cellular')

    def test_stale_or_disconnected_cellular_falls_back_immediately(self):
        for reason in ('stale', 'disconnect'):
            with self.subTest(reason=reason):
                self.route_sample()
                self.route_sample()
                if reason == 'stale':
                    self.agent.cached['evidence_at'] -= 30
                else:
                    self.modem.registered = False
                    self.agent.sample(True)
                self.agent.reconcile_routes()
                self.assertEqual(self.network.mode, 'wifi')
                self.modem.registered = True
                self.route_sample()
                self.assertEqual(self.network.mode, 'wifi')
                self.route_sample()
                self.assertEqual(self.network.mode, 'cellular')

    def test_ready_task_retains_no_stale_cellular_default_and_does_not_write_modem(self):
        self.route_sample()
        self.route_sample()
        self.agent.create('setup', self.config['revision'])
        self.agent.cached['evidence_at'] -= 30
        self.agent.reconcile_routes()
        self.assertEqual(self.network.mode, 'wifi')
        self.assertFalse(self.modem.calls)

    def test_route_prepare_failure_falls_back_and_new_proof_is_required(self):
        self.route_sample()
        self.route_sample()
        self.network.failure = 'prepare'
        with self.assertRaises(ValueError):
            self.agent.reconcile_routes()
        self.assertEqual(self.network.mode, 'wifi')
        self.network.failure = None
        self.route_sample()
        self.assertEqual(self.network.mode, 'wifi')
        self.route_sample()
        self.assertEqual(self.network.mode, 'cellular')

    def test_maintenance_switches_to_wifi_before_releasing_serial(self):
        self.route_sample()
        self.route_sample()
        self.agent.set_maintenance(True)
        self.assertEqual(self.network.mode, 'wifi')
        self.agent.set_maintenance(False)
        self.route_sample()
        self.assertEqual(self.network.mode, 'wifi')

    def test_routing_mode_survives_sampling_without_repeated_transition_events(self):
        with patch.object(self.agent.store, 'event') as event:
            for _ in range(5):
                self.route_sample()
        transitions = [call for call in event.call_args_list if call.args[0] == 'routing']
        self.assertEqual(len(transitions), 2)
        self.assertEqual(self.agent.status()['routing']['mode'], 'cellular')

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

    def test_cancel_ready_and_paused_tasks_resumes_idle_probes(self):
        for state in ("ready", "paused"):
            with self.subTest(state=state):
                job = self.agent.create("setup", self.config["revision"], {"mode": "manual"})
                if state == "paused":
                    job = self.wait(job)
                self.assertEqual(job["state"], state)
                result = self.agent.cancel_job(job["id"])
                self.assertEqual(result["state"], "cancelled")
                self.assertIsNone(self.agent.current)
                self.assertTrue(self.agent.store.setting("recovery_paused"))
                # No replacement job or restart may be needed for observation.
                for _ in range(2):
                    sample = self.agent.sample(True)
                    self.assertEqual(sample["quality"], "ok")
                    self.assertTrue(sample["connected"])

    def test_recovery_records_failed_precheck_before_bounded_repair(self):
        self.network.failure = "probe"
        job = self.agent.create("recover", self.config["revision"])
        result = self.wait(job)
        self.assertFalse(result["result"]["initial_verification"]["connected"])
        self.assertIn("prepare", self.network.calls)
        self.assertLessEqual(sum(call[0] == "cfun0" for call in self.modem.calls), 1)
        self.assertEqual(result["state"], "failed")

    def test_uncertain_power_off_restores_in_setup_and_recovery_tasks(self):
        for kind, cancel, restore_failure in (("setup", False, False), ("recover", False, False),
                                              ("recover", True, False), ("recover", False, True)):
            with self.subTest(kind=kind, cancel=cancel, restore_failure=restore_failure):
                self.agent.store.set("last_reset", 0)
                self.modem.functionality = 1
                self.modem.registered = False
                self.modem.active.clear()
                self.modem.calls.clear()
                adapter = Modem(self.config)
                adapter.fingerprint = self.modem.fingerprint
                simulated_write = self.modem.write

                def exchange(command, timeout=3, optional=False):
                    if command in ("AT+CFUN=0", "AT+CFUN=1"):
                        operation = "cfun" + command[-1]
                        if restore_failure and operation == "cfun1":
                            self.modem.calls.append((operation, None))
                            raise TimeoutError("Power restore transport failed")
                        simulated_write(operation)
                        if operation == "cfun0":
                            if cancel:
                                self.agent.cancel.set()
                            raise TimeoutError("Power-off acknowledgement lost")
                    return self.modem.query(command)

                adapter.exchange = exchange
                job = self.agent.create(kind, self.config["revision"])
                with patch.object(self.modem, "write", side_effect=adapter.write):
                    self.agent.execute(job)
                result = self.agent.store.get_job(job["id"])
                self.assertEqual(result["state"], "cancelled" if cancel else "failed")
                self.assertIn("Power-off acknowledgement lost", result["error"])
                if restore_failure:
                    self.assertIn("power restoration failed", result["error"])
                self.assertEqual(self.modem.functionality, 0 if restore_failure else 1)
                self.assertEqual([call[0] for call in self.modem.calls], ["cfun0", "cfun1"])
                self.assertTrue(self.agent.store.setting("recovery_paused"))
                self.assertFalse(adapter.power_restore_authorized)
                self.assertIsNone(self.agent.current)

    def test_failed_management_guard_does_not_attempt_power_compensation(self):
        with patch.object(self.network, "snapshot", return_value={"management_protected": False}), \
                self.assertRaises(Conflict):
            self.agent.write("cfun0")
        self.assertEqual(self.modem.calls, [])

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
