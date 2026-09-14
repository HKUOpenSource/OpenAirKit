import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import os

from aoc_spark.connectivity import Reachability, connection_state
from aoc_spark.domain import fresh_snapshot, observation, utc, stale_entity, service_health
from aoc_spark.resources import Resources


def device():
    at = utc()
    return dict(id='ocudu:ue:test', stack='ocudu', epoch='amf-run', identity='Subscriber ****0001',
                source='open5gs_pdu_info', registration='registered', status='ok', state='registered',
                observed_at=at, identifiers={'ran_ue_ngap_id': '7'}, metrics=[], sessions=[
                    dict(id='1', dnn='oai', address='10.0.0.2', status='ok', state='active', observed_at=at)])


def runner(code):
    return Mock(side_effect=lambda argv, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps([
        dict(gateway='172.28.81.14', dev='eth0')])) if 'route' in argv else SimpleNamespace(returncode=code, stdout='1 packets transmitted, 0 received'))


class ConnectionTests(unittest.TestCase):
    def test_host_cpu_capacity_used_cores_and_ratio_are_distinct(self):
        from aoc_spark.collector import cpu_sample
        previous, usage, capacity = cpu_sample('cpu 10 0 10 80 0 0 0 0', capacity=20)
        self.assertIsNone(usage)
        _, usage, capacity = cpu_sample('cpu 20 0 20 140 0 0 0 0', previous, 20)
        self.assertEqual(capacity, 20)
        self.assertAlmostEqual(usage, .25)
        self.assertEqual(usage * capacity, 5)

    def test_container_cpu_capacity_and_host_share_are_distinct(self):
        inspected = {'aoc-v2-open5gs-amf-1': {
            'State': {'Running': True},
            'HostConfig': {'NanoCpus': 2_000_000_000, 'CpusetCpus': '5-9'}}}
        row = {'Name': 'aoc-v2-open5gs-amf-1', 'CPUPerc': '150.00%', 'MemUsage': '100MiB / 2GiB'}
        with patch('aoc_spark.resources.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(row))):
            values = {item['name']: item['value'] for item in Resources(Mock()).containers(inspected)['aoc-v2-open5gs-amf-1']}
        self.assertEqual(values['cpu_cores'], 1.5)
        self.assertEqual(values['cpu_capacity'], 2)
        self.assertEqual(values['cpu_utilization'], .75)
        self.assertAlmostEqual(values['cpu_host_share'], 1.5 / (os.cpu_count() or 1))

    def test_collector_does_not_probe_by_default(self):
        from aoc_spark.collector import Collector
        def run(argv, **kwargs):
            if argv[:2] == ['systemctl', 'show']:
                return 'ActiveState=active\nMainPID=0\nInvocationID=test'
            return ''
        with patch('aoc_spark.collector.run', side_effect=run), patch('aoc_spark.collector.subprocess.run') as command, patch('aoc_spark.collector.SchedulerFeed.get', return_value=None), patch('aoc_spark.collector.Open5GS.collect', return_value={'devices': [], 'observations': [], 'gnb': {}, 'errors': {}}):
            command.return_value.stdout = '[]'
            collector = Collector()
            collector.reachability.collect = Mock()
            try:
                result = collector.collect()
                self.assertEqual(result['active_stack'], 'ocudu')
                collector.reachability.collect.assert_not_called()
            finally:
                collector.pool.shutdown()

    def test_registration_reports_do_not_claim_connected(self):
        d = device()
        connection_state(d)
        self.assertEqual(d['state'], 'registered')
        self.assertEqual(set(d['connection']['layers']), {'registration', 'radio', 'data_pdu'})
        d['registration'] = 'deregistered'
        connection_state(d)
        self.assertEqual(d['state'], 'disconnected')

    def test_pdu_address_and_rrc_idle_do_not_claim_data_reachability_or_disconnect(self):
        d = device()
        connection_state(d)
        self.assertEqual(d['state'], 'registered')
        self.assertEqual(d['connection']['reason'], 'registration_not_data_connectivity')
        radio = device()
        radio.update(source='ocudu_scheduler', registration='unknown', state='idle', sessions=[])
        connection_state(radio)
        self.assertEqual(radio['state'], 'idle')
        self.assertEqual(radio['connection']['reason'], 'radio_context_not_subscriber_connection')

    def test_two_distinct_probes_and_epoch_reset(self):
        now = [0]
        run = runner(0)
        probe = Reachability(run, lambda: now[0])
        d = device()
        probe.collect([d], 'ocudu', 'gnb-1')
        self.assertEqual(d['reachability']['state'], 'pending')
        probe.collect([d], 'ocudu', 'gnb-1')
        self.assertEqual(run.call_count, 2)
        now[0] = 11
        probe.collect([d], 'ocudu', 'gnb-1')
        self.assertEqual(d['reachability']['state'], 'reachable')
        self.assertEqual(run.call_args.args[0][-1], '10.0.0.2')
        probe.collect([d], 'ocudu', 'gnb-2')
        self.assertEqual(d['reachability']['state'], 'pending')
        self.assertEqual(stale_entity(d)['reachability']['state'], 'unknown')

    def test_scope_duplicate_and_wrong_route(self):
        probe = Reachability(runner(2))
        d = device()
        probe.collect([d], 'ocudu', 'run')
        self.assertEqual(d['reachability']['state'], 'unknown')
        other = copy.deepcopy(d); other['id'] = 'other'
        probe.execute.reset_mock()
        probe.collect([d, other], 'ocudu', 'run')
        probe.execute.assert_not_called()
        self.assertEqual(d['reachability']['reason'], 'ambiguous_address_owner')
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout='[{"gateway":"172.28.81.1","dev":"eth0"}]'))
        Reachability(run).collect([device()], 'ocudu', 'run')
        self.assertEqual(run.call_count, 1)

    def test_expired_session_and_health(self):
        d = device()
        d['sessions'][0]['observed_at'] = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
        sample = dict(observed_at=utc(), active_stack='ocudu', observations=[
            observation('sessions', 'ocudu:oai', 'reported_pdu_count', 1, 'count')], devices=[d])
        result = fresh_snapshot(sample)
        self.assertEqual(result['devices'][0]['sessions'][0]['status'], 'stale')
        self.assertEqual(result['observations'][0]['value'], 0)
        self.assertEqual(service_health({'state': 'unknown', 'health': 'unsupported'}), 'unknown')

    def test_health_has_only_v2_dimensions(self):
        metrics = [observation('host', 'spark', k, v) for k, v in {
            'memory_used': 98, 'memory_total': 100, 'disk_used': 10, 'disk_total': 100,
            'b210_devices': 1, 'b210_speed': '5000', 'b210_holder_pids': [42]}.items()]
        metrics += [observation('ran', 'ocudu', 'radio_process', 'active'),
                    observation('ran', 'ocudu', 'radio_pid', 42), observation('ran', 'ocudu', 'n2_associated', True)]
        sample = dict(observed_at=utc(), active_stack='ocudu', observations=metrics, devices=[], services=[])
        result = fresh_snapshot(sample)
        self.assertEqual(set(result['health']), {'ocudu'})
        self.assertEqual(set(result['health']['ocudu']), {'host', 'b210', 'ran', 'core'})
        self.assertEqual(result['health']['ocudu']['host'], 'failed')


if __name__ == '__main__':
    unittest.main()
