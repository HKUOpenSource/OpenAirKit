import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aoc_spark.storage import Store
from aoc_spark.telemetry import RadioEvents, RadioIdentity, SchedulerFeed, parse_control, parse_ocudu
from aoc_spark.traffic import Traffic, rules
from aoc_spark.domain import utc


def scheduler_payload(du_ue_id=0, rnti=123):
    return {'cells': [{'cell_metrics': {'pci': 666}, 'ue_list': [{
        'rnti': rnti, 'ue': du_ue_id, 'dl_brate': 23_000_000, 'ul_brate': 5_000_000,
        'cqi': -1, 'dl_mcs': 27, 'ul_mcs': 25, 'pusch_snr_db': 12, 'pusch_rsrp_db': -105,
        'phr': 13, 'dl_ri': 1, 'ul_ri': 1, 'dl_nof_ok': 9, 'dl_nof_nok': 1,
        'ul_nof_ok': 0, 'ul_nof_nok': 0}]}]}


def subscriber(at=None):
    at = at or utc()
    return dict(id='ocudu:ue:subscriber', stack='ocudu', epoch='open5gs-run',
                identity='Subscriber ****0001', identifiers={'ran_ue_ngap_id': '7'},
                registration='registered', observed_at=at, source='open5gs_pdu_info',
                status='ok', state='registered', metrics=[], sessions=[
                    dict(id='1', dnn='oai', address='10.0.0.2', status='ok', state='active',
                         observed_at=at, source='open5gs_pdu_info')])


class TelemetryTests(unittest.TestCase):
    def test_scheduler_units_unknown_cqi_no_blocks_and_epoch(self):
        devices, values = parse_ocudu(scheduler_payload(), 'boot-a')
        self.assertEqual(values[0]['value'], 23_000_000)
        metrics = {v['name']: v for v in devices[0]['metrics']}
        self.assertEqual(metrics['dl_bler']['value'], 0.1)
        self.assertIsNone(metrics['ul_bler']['value'])
        self.assertEqual(metrics['cqi']['status'], 'unavailable')
        self.assertEqual(metrics['sinr']['value'], 12)
        self.assertEqual(metrics['dl_mcs']['value'], 27)
        self.assertIsNone(metrics['ul_mcs']['value'])
        self.assertEqual(metrics['ul_mcs']['reason'], 'no_transport_blocks')
        self.assertIsNone(metrics['ul_bps']['value'])
        self.assertEqual(metrics['ul_harq_ok']['value'], 0)
        aggregated = {value['name']: value for value in values}
        self.assertEqual(aggregated['dl_mcs']['value'], 27)
        self.assertEqual(aggregated['dl_harq_nok']['value'], 1)
        self.assertIsNone(aggregated['rrc_connected']['value'])
        self.assertEqual(aggregated['rrc_connected']['reason'], 'current_rrc_state_not_reported')
        self.assertEqual(aggregated['radio_contexts']['value'], 1)
        self.assertNotEqual(devices[0]['id'], parse_ocudu(scheduler_payload(), 'boot-b')[0][0]['id'])
        self.assertIsNone(parse_ocudu({'status': 'ok'}, 'boot'))

    def test_scheduler_validation_and_identifier_reuse(self):
        self.assertRaises(ValueError, parse_ocudu, {'cells': [{'cell_metrics': {}, 'ue_list': ['bad']}]}, 'run')
        ids = RadioIdentity()
        first = ids.apply(parse_ocudu(scheduler_payload(1), 'run')[0])[0]
        again = ids.apply(parse_ocudu(scheduler_payload(2), 'run')[0])[0]
        self.assertNotEqual(first['id'], again['id'])
        self.assertEqual(first['identity'], 'RNTI 007b')

    def test_control_metrics_are_allowlisted(self):
        payload = {'cu-cp': {'rrcs': {'du': [
            {'rrc_connection_number': {'mean_nof_rrc_connections': 1, 'max_nof_rrc_connections': 2}},
            {'rrc_connection_number': {'mean_nof_rrc_connections': 3, 'max_nof_rrc_connections': 4}},
        ]}}}
        values = {v['name']: v for v in parse_control(payload)}
        self.assertEqual(values['rrc_mean_connections']['value'], 4)
        self.assertEqual(values['rrc_peak_connections']['value'], 6)

    def test_restart_invalidates_scheduler_sample(self):
        feed = SchedulerFeed()
        feed.started = True
        feed.epoch = 'first'
        feed.sample = parse_ocudu(scheduler_payload(), 'first')
        self.assertIsNotNone(feed.get('first'))
        self.assertIsNone(feed.get('second'))

    def test_radio_event_reader_is_incremental_and_counts_current_window(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'gnb.log'
            path.write_text('existing historical underflow\n')
            events = RadioEvents()
            from unittest.mock import patch
            with patch('aoc_spark.telemetry.Path', return_value=path):
                self.assertEqual(events.read('ocudu', 'run'), [])
                with path.open('a') as output:
                    output.write('RF underflow\nlate command\noverflow\n')
                current = {item['name']: item for item in events.read('ocudu', 'run')}
            self.assertEqual(current['log_underflows']['value'], 1)
            self.assertEqual(current['log_lates']['value'], 1)
            self.assertEqual(current['log_overflows']['value'], 1)


class HistoryTests(unittest.TestCase):
    def test_first_seen_survives_store_restart(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / 'data.db')
            first = utc()
            store.ingest(dict(observed_at=first, devices=[subscriber(first)]))
            later = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
            restarted = Store(store.path)
            restarted.ingest(dict(observed_at=later, devices=[subscriber(later)]))
            self.assertEqual(restarted.entity('ocudu:ue:subscriber', 'device')['first_seen'], first)

    def test_migration_backup_history_and_event_cursor(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / 'data.db')
            at = utc(); device = subscriber(at)
            sample = dict(observed_at=at, devices=[device], events=[
                dict(id='a', at=at, stack='ocudu', level='info', kind='device_change', message='first'),
                dict(id='b', at=at, stack='ocudu', level='info', kind='radio_state', message='second')])
            store.ingest(sample); store.ingest(sample)
            self.assertEqual(len(store.entities('device', 'ocudu')), 1)
            self.assertEqual(store.events(1, stack='ocudu')[0]['id'], 'b')
            self.assertEqual(store.events(1, stack='ocudu', cursor='b')[0]['id'], 'a')
            self.assertEqual(store.events(2, stack='ocudu', kind='device_change')[0]['kind'], 'device_change')
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE name='switch_jobs'").fetchone()[0], 0)
                db.execute('PRAGMA user_version=0')
            Store(store.path)
            self.assertEqual(len(list(Path(root).glob('*.before-v5-*.db'))), 1)

    def test_counter_direction_reset_and_v2_rules(self):
        counts = {'nftables': [{'counter': {'name': 'n3_ul', 'bytes': 100}},
                               {'counter': {'name': 'n3_dl', 'bytes': 200}}]}
        reader = Traffic(lambda _: json.dumps(counts))
        container = {'State': {'Pid': 1, 'Running': True, 'StartedAt': 'first'}}
        self.assertIsNone(reader.collect('ocudu', container)['n3'][0]['value'])
        counts['nftables'][0]['counter']['bytes'] = 50
        self.assertIsNone(reader.collect('ocudu', container)['n3'][0]['value'])
        nft = rules('ocudu')
        self.assertIn('ip saddr 172.28.81.1 ip daddr 172.28.81.14', nft)
        self.assertIn('iifname "ogstun" oifname "eth0"', nft)
        self.assertNotIn('tun0', nft)
        self.assertNotIn('masquerade', nft)
        with self.assertRaises(ValueError):
            rules('legacy')


if __name__ == '__main__':
    unittest.main()
