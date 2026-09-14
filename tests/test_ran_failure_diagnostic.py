import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('ran_diagnostic', Path(__file__).resolve().parents[1] / 'scripts/ran_failure_diagnostic.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class DiagnosticTests(unittest.TestCase):
    def test_window_filter_redaction_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'gnb.log'
            path.write_text('\n'.join([
                '2026-09-08T09:30:00 [RF      ] [W] Real-time failure in RF: underflow',
                '2026-09-08T09:33:44 [NGAP    ] [W] PDU Session failed IMSI 001010000000001',
                '2026-09-08T09:33:44 [PHY     ] [I] raw data must not be exported',
                '2026-09-08T09:37:00 [RRC     ] [W] security failure ' + 'a' * 32,
            ]) + '\n')
            before = path.read_bytes()
            result = diagnostic.scan(path)
            self.assertTrue(result['covers_window'])
            self.assertEqual(len(result['window_events']), 1)
            self.assertEqual(len(result['recent_events']), 2)
            self.assertEqual(path.read_bytes(), before)
            encoded = json.dumps(result)
            for secret in ('001010000000001', 'a' * 32, 'raw data'):
                self.assertNotIn(secret, encoded)
            partial = diagnostic.scan(path, max_bytes=100)
            self.assertFalse(partial['covers_window'])
            self.assertGreater(partial['scan_offset'], 0)

    def test_config_export_uses_field_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'gnb.json'
            path.write_text(json.dumps({'ru_sdr': {'srate': 23.04, 'device_args': 'serial=private'},
                                        'password': 'secret', 'log': {'all_level': 'info'}}))
            result = diagnostic.config_summary(path)
            self.assertEqual(result['ru_sdr'], {'srate': 23.04})
            self.assertNotIn('private', json.dumps(result))
            self.assertNotIn('secret', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
