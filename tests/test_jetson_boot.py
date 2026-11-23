import contextlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('jetson_boot', ROOT / 'deploy/jetson/boot_connect.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class Clock:
    def __init__(self):
        self.now = 1000.

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def status(now):
    return {'quality': 'ok', 'connected': True, 'registered': True, 'lab_policy_match': True,
            'management_protected': True, 'evidence_at': now, 'maintenance': False,
            'active_job': None, 'recovery_paused': False,
            'network': {'data_interface': 'cell0', 'data_address': '192.0.2.2'},
            'routing': {'mode': 'cellular'},
            'probes': {k: {'state': 'ok', 'at': now, 'interface': 'cell0', 'source': '192.0.2.2'}
                       for k in ('gateway', 'upf', 'ext_dn', 'public')}}


class ProofTests(unittest.TestCase):
    def test_all_probes_must_match_current_interface_and_source(self):
        self.assertIsNotNone(b.proof(status(1000), 1000))
        for field, value in [('interface', 'wifi0'), ('source', '192.0.2.3'), ('state', 'failed'), ('at', 900)]:
            sample = status(1000)
            sample['probes']['public'][field] = value
            self.assertIsNone(b.proof(sample, 1000))

    def test_missing_or_stale_evidence_cannot_pass(self):
        for field, value in [('evidence_at', 900), ('registered', False), ('connected', False), ('management_protected', False)]:
            sample = status(1000)
            sample[field] = value
            self.assertIsNone(b.proof(sample, 1000))
        sample = status(1000)
        sample['probes'].pop('upf')
        self.assertIsNone(b.proof(sample, 1000))

    def observe(self, change=lambda v, t: None):
        clock, report = Clock(), {}

        def rpc(request):
            value = status(clock.now)
            change(value, clock.now)
            return value
        with patch.object(b, 'rpc', rpc), patch.object(b, 'management', lambda c: None):
            b.wait_data({}, report, lambda: None, clock.time, clock.time, clock.sleep)
        return report

    def test_full_120_seconds_and_two_distinct_sets_required(self):
        result = self.observe()
        self.assertGreaterEqual(result['healthy_seconds'], 120)
        self.assertGreaterEqual(result['fresh_probe_sets'], 2)

    def test_late_promotion_gets_full_observation(self):
        result = self.observe(lambda v, t: v['routing'].update(mode='wifi') if t < 1140 else None)
        self.assertGreaterEqual(result['healthy_seconds'], 120)

    def test_radio_loss_during_observation_fails(self):
        with self.assertRaises(ValueError):
            self.observe(lambda v, t: v.update(registered=False) if t > 1034 else None)

    def test_paused_recovery_does_not_pass_final_acceptance(self):
        with self.assertRaises(ValueError):
            self.observe(lambda v, t: v.update(recovery_paused=True))

    def test_wifi_only_times_out(self):
        with self.assertRaises(TimeoutError):
            self.observe(lambda v, t: v['routing'].update(mode='wifi'))


class BoundaryTests(unittest.TestCase):
    def test_only_target_selection_and_read_commands_allowed(self):
        modem = b.Serial({'network': {'plmn': '00101'}})
        for command in ('AT+CRSM=214,28539,0,0,3', 'AT+CFUN=1,1', 'AT+QCFG="usbspeed","20"', 'AT+COPS=1,2,"00102",12'):
            with self.assertRaises(ValueError):
                modem.exchange(command)

    def test_unknown_completion_blocks_queries(self):
        modem = b.Serial({'network': {'plmn': '00101'}})
        modem.known = False
        with self.assertRaises(RuntimeError):
            modem.query('AT')

    def test_no_selection_replay(self):
        modem = b.Serial({'network': {'plmn': '00101'}})
        with self.assertRaises(ValueError):
            modem.select_once({'selection': {'terminal': False}}, lambda: None)

    def test_selection_intent_is_saved_before_send(self):
        modem = b.Serial({'network': {'plmn': '00101'}})
        events, report = [], {}
        modem.verify = lambda: None
        modem.exchange = lambda q, **kw: events.append(('send', q)) or ['+CME ERROR: 30']
        with patch.object(b, 'management', lambda c: None):
            modem.select_once(report, lambda: events.append(('save', copy.deepcopy(report))))
        self.assertEqual(events[0], ('save', {'selection': {'terminal': False}}))
        self.assertTrue(report['selection']['terminal'])
        self.assertFalse(report['selection']['accepted'])

    def test_configuration_ignores_runtime_addresses_but_not_dnn(self):
        q = 'AT+CGDCONT?'
        a = ['+CGDCONT: 5,"IP","lab","0.0.0.0",0,0', 'OK']
        z = ['+CGDCONT: 5,"IP","lab","192.0.2.10",0,0', '+CGDCONT: 22,"IPV4V6","","0.0.0.0",0,0', 'OK']
        self.assertEqual(b.canonical(q, a), b.canonical(q, z))
        with self.assertRaises(ValueError):
            b.check_preserved({q: b.canonical(q, a)}, {q: b.canonical(q, [x.replace('lab', 'other') for x in z])})

    def test_public_and_private_modes_are_explicit_under_restrictive_umask(self):
        with tempfile.TemporaryDirectory() as temp:
            old = os.umask(0o077)
            try:
                public, private = Path(temp) / 'public.json', Path(temp) / 'private.json'
                b.atomic(public, {'ok': True}, 0o644)
                b.atomic(private, {'private': True})
                self.assertEqual(public.stat().st_mode & 0o777, 0o644)
                self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            finally:
                os.umask(old)


class LifecycleTests(unittest.TestCase):
    def simulate(self, scenario='natural', rerun=False):
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            directory = Path(temp)
            (directory / 'private').mkdir()
            (directory / 'public').mkdir()
            clock, calls = Clock(), []
            control = {'maintenance': False}
            config = {'revision': 'reviewed', 'network': {'plmn': '00101'}}

            class Serial:
                known = True

                def __init__(self, config):
                    self.config = config

                def __enter__(self):
                    return self

                def __exit__(self, *unused):
                    return None

                def wait_sim(self):
                    if scenario == 'sim_mismatch':
                        raise ValueError('different SIM')

                def select_once(self, report, save):
                    calls.append('selection')
                    report['selection'] = {'terminal': False}
                    save()
                    if scenario == 'unknown':
                        self.known = False
                        raise TimeoutError('unknown')
                    report['selection'].update(terminal=True, accepted=False, response=['+CME ERROR: 30'])
                    save()

                def query(self, command):
                    return ['+QNWPREFCFG: "mode_pref",NR5G', 'OK']

            def rpc(request):
                calls.append(request['op'])
                if request['op'] == 'status':
                    return {**status(clock.now), 'maintenance': control['maintenance']}
                if request['op'] == 'maintenance':
                    control['maintenance'] = request['enabled']
                    return {}
                if request['op'] == 'create':
                    return {'id': 'task-one'}
                if request['op'] == 'job':
                    return {'id': 'task-one', 'state': 'failed' if scenario == 'job_failure' else 'complete'}
                return {}

            waits = []

            def wait_target(modem, seconds):
                waits.append(seconds)
                return scenario == 'natural' or len(waits) >= 2 and scenario != 'not_registered'

            for name, value in [('STATE', directory), ('current_boot_id', lambda: 'test-boot'),
                                ('Serial', Serial), ('rpc', rpc), ('wait_ready', lambda *a: {}),
                                ('management', lambda c: {}), ('configuration', lambda m: {'protected': True}),
                                ('usb_speed', lambda c: '480'), ('wait_target', wait_target)]:
                stack.enter_context(patch.object(b, name, value))
            stack.enter_context(patch.object(b.time, 'monotonic', clock.time))
            stack.enter_context(patch.object(b.time, 'time', clock.time))
            stack.enter_context(patch.object(b.time, 'sleep', clock.sleep))
            # Exercise actual acceptance, with its clocks explicitly injected.
            real_wait = b.wait_data
            stack.enter_context(patch.object(b, 'wait_data', lambda c, r, s: real_wait(c, r, s, clock.time, clock.time, clock.sleep)))
            site = {'modem_configuration': {'protected': True}, 'usb_speed_mbps': '480'}
            result = b.connect(site, config)
            report = json.loads((directory / 'public/status.json').read_text())
            if rerun:
                count = len(calls)
                with self.assertRaises((ValueError, BlockingIOError)):
                    b.connect(site, config)
                self.assertEqual(len(calls), count)
            return result, report, calls, control

    def test_natural_reconnection_uses_no_operator_selection(self):
        code, report, calls, control = self.simulate(rerun=True)
        self.assertEqual(code, 0)
        self.assertNotIn('selection', calls)
        self.assertEqual(calls.count('create'), 1)
        self.assertEqual(calls.count('run'), 1)
        self.assertTrue(report['automatic_recovery_active'])
        self.assertGreaterEqual(report['healthy_seconds'], 120)
        self.assertFalse(control['maintenance'])

    def test_delayed_registration_after_known_rejection_can_pass(self):
        code, report, calls, control = self.simulate('select')
        self.assertEqual(code, 0)
        self.assertEqual(calls.count('selection'), 1)
        self.assertFalse(report['selection']['accepted'])

    def test_unknown_selection_holds_maintenance_without_standard_task(self):
        code, report, calls, control = self.simulate('unknown')
        self.assertEqual(code, 1)
        self.assertTrue(report['maintenance_retained'])
        self.assertNotIn('create', calls)
        self.assertTrue(control['maintenance'])

    def test_sim_mismatch_never_selects_or_launches_setup(self):
        code, report, calls, control = self.simulate('sim_mismatch')
        self.assertEqual(code, 1)
        self.assertNotIn('selection', calls)
        self.assertNotIn('create', calls)
        self.assertFalse(control['maintenance'])

    def test_failed_standard_task_never_replayed(self):
        code, report, calls, control = self.simulate('job_failure')
        self.assertEqual(code, 1)
        self.assertEqual(report['job_state'], 'failed')
        self.assertEqual(calls.count('run'), 1)

    def test_registration_failure_resumes_wifi_observation(self):
        code, report, calls, control = self.simulate('not_registered')
        self.assertEqual(code, 1)
        self.assertEqual(calls.count('selection'), 1)
        self.assertFalse(control['maintenance'])
        self.assertNotIn('create', calls)


if __name__ == '__main__':
    unittest.main()
