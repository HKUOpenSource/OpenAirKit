import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v2runtime', ROOT / 'deploy/spark/stack/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class V2RuntimeTests(unittest.TestCase):
    def check_health(self, names, actual=None, unhealthy=None):
        actual = names if actual is None else actual
        items = [{'Config': {'Labels': {'com.docker.compose.service': name,
                  'org.agentic-ocudu.owner': runtime.PROJECT, 'com.docker.compose.project': runtime.PROJECT}}, 'Image': 'verified',
                  'State': {'Running': True, 'Health': {'Status':
                  'unhealthy' if name == unhealthy else 'healthy'}}} for name in actual]
        with patch.object(runtime, 'containers', return_value=items), \
                patch.object(runtime, 'compose', return_value='\n'.join(names)):
            runtime.core_ready({'addresses': dict.fromkeys(set(names) | set(actual)),
                                'images': {'nf': 'verified'}})

    def test_health_uses_exact_compose_membership_for_10_11_12_services(self):
        for size in (10, 11, 12):
            self.check_health(['nf%d' % i for i in range(size)])

    def test_health_rejects_missing_extra_duplicate_unhealthy_or_empty(self):
        for names, actual, unhealthy, reason in (
                (['amf', 'smf'], ['amf'], None, 'missing'),
                (['amf', 'smf'], ['amf', 'other'], None, 'extra'),
                (['amf', 'smf'], ['amf', 'amf'], None, 'duplicates'),
                (['amf', 'smf'], None, 'smf', 'unhealthy'),
                ([], [], None, 'empty')):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.check_health(names, actual, unhealthy)

    def test_association_requires_exact_pid_local_and_amf(self):
        text = 'ESTAB 0 0 172.28.81.1:4567 172.28.81.12:38412 users:(("gnb",pid=42,fd=9))'
        self.assertTrue(runtime.association(text, 42))
        self.assertFalse(runtime.association(text, 4))
        self.assertFalse(runtime.association(text.replace('.12:38412', '.13:38412'), 42))
        self.assertFalse(runtime.association(text.replace('81.1:', '81.10:'), 42))

    def test_unowned_container_cannot_be_stopped(self):
        item = {'Config': {'Labels': {'com.docker.compose.service': 'upf'}}, 'Image': 'verified'}
        with self.assertRaises(ValueError):
            runtime.owned([item], {'addresses': {'upf': 'x'}, 'images': {'upf': 'verified'}})

    def test_changed_or_escaped_release_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'file').write_text('expected')
            expected = runtime.digest(path / 'file')
            runtime.verify_tree(path, {'file': expected})
            (path / 'file').write_text('changed')
            with self.assertRaises(ValueError):
                runtime.verify_tree(path, {'file': expected})
            with self.assertRaises(ValueError):
                runtime.verify_tree(path, {'../file': expected})

    def test_failed_stop_does_not_remove_evidence_or_volume(self):
        item = {'State': {'Running': False, 'ExitCode': 137, 'OOMKilled': False},
                'Config': {'Labels': {'org.agentic-ocudu.owner': runtime.PROJECT, 'com.docker.compose.project': runtime.PROJECT,
                                     'com.docker.compose.service': 'upf'}}, 'Image': 'verified'}
        with patch.object(runtime, 'containers', return_value=[item]), patch.object(runtime, 'compose') as compose, patch.object(runtime, 'record'):
            with self.assertRaises(ValueError):
                runtime.core_stop({'addresses': {'upf': 'x'}, 'images': {'upf': 'verified'}})
            self.assertEqual(compose.call_args_list[0].args, ('stop', '--timeout', '20'))
            self.assertEqual(compose.call_count, 1)

    def test_config_is_single_data_radio_without_telemetry(self):
        config = runtime.radio_config('123abc')
        self.assertEqual(config['cell_cfg']['dl_arfcn'], 643392)
        self.assertEqual(config['ru_sdr']['rx_gain'], 54)
        self.assertEqual(config['cell_cfg']['pusch'], {'max_ue_mcs': 24})
        self.assertEqual(config['cu_cp']['amf']['addrs'], '172.28.81.12')
        self.assertEqual(config['remote_control'], {'enabled': False})
        self.assertEqual(config['log']['all_level'], 'warning')
        self.assertEqual(config['log']['cu_level'], 'info')
        self.assertEqual(config['log']['ngap_level'], 'info')
        self.assertNotIn('ims', json.dumps(config))
        with self.assertRaises(ValueError):
            runtime.radio_config('serial,other=1')

    def test_ng_setup_requires_current_infoapi_success(self):
        from io import BytesIO
        spec = {'addresses': {'amf': '172.28.81.12'}}
        for payload, expected in (({'items': []}, False),
                                  ({'items': [{'ng': {'setup_success': False}}]}, False),
                                  ({'items': [{'ng': {'setup_success': True}}]}, True)):
            with patch.object(runtime.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value = BytesIO(json.dumps(payload).encode())
                self.assertEqual(runtime.n2_ready(spec), expected)

    def test_failed_radio_start_preserves_core_and_reports_failure(self):
        calls = []
        def run(argv, timeout=30):
            calls.append(argv)
            raise RuntimeError('Synthetic startup failure')
        with patch('sys.argv', ['aocctl', 'start']), patch.object(runtime.os, 'geteuid', return_value=0), \
                patch.object(runtime, 'manifest', return_value={}), patch.object(runtime, 'resources'), \
                patch.object(runtime, 'usb_free'), patch.object(runtime, 'lock', return_value=nullcontext()), \
                patch.object(runtime, 'show', return_value={'ActiveState': 'inactive'}), \
                patch.object(runtime, 'record') as record, patch.object(runtime, 'run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'startup failure'):
                runtime.main()
            record.assert_called_with('start-failed', inspection_required=True)
        self.assertEqual(calls, [['systemctl', 'start', runtime.UNITS[0]]])

    def test_failed_radio_stop_does_not_stop_core(self):
        with patch.object(runtime, 'run') as run, patch.object(runtime, 'show', return_value={
                'ActiveState': 'failed', 'Result': 'signal'}):
            with self.assertRaisesRegex(ValueError, 'Radio failure retained'):
                runtime.stop({})
        run.assert_called_once_with(['systemctl', 'stop', runtime.UNITS[0]], 60)



if __name__ == '__main__':
    unittest.main()
