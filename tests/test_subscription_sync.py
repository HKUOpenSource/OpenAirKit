"""Insert-only transfer decisions and failure boundaries; no production secrets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('subscription_sync', ROOT / 'deploy/maintenance/sync-subscriptions.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def candidate(self, suffix='1'):
        return sync.subscriber_module().document({
            'imsi': '46003000000000' + suffix, 'ki': '00' * 16,
            'opc': '11' * 16, 'amf': '8000'})

    def test_existing_sqn_and_policy_are_preserved(self):
        candidate = self.candidate()
        old = copy.deepcopy(candidate)
        old['security']['sqn'] = {'$numberLong': '123456'}
        old['slice'][0]['session'][0]['qos']['index'] = 7
        baseline = copy.deepcopy(old)
        self.assertEqual(sync.plan([candidate, self.candidate('2')], [old]), [self.candidate('2')])
        self.assertEqual(old, baseline)

    def test_any_static_conflict_blocks_whole_plan(self):
        for field in ('k', 'opc', 'amf'):
            with self.subTest(field=field):
                old = self.candidate()
                old['security'][field] = 'ff'
                with self.assertRaises(sync.Refused):
                    sync.plan([self.candidate('2'), self.candidate()], [old])

    def test_op_instead_of_opc_is_not_silently_accepted(self):
        old = self.candidate()
        old['security']['op'] = '22' * 16
        with self.assertRaises(sync.Refused):
            sync.plan([self.candidate()], [old])

    def test_duplicate_target_is_rejected(self):
        with self.assertRaises(sync.Refused):
            sync.plan([self.candidate()], [self.candidate(), self.candidate()])

    def test_existing_unchanged_includes_sqn_and_unrelated_fields(self):
        before = self.candidate()
        self.assertTrue(sync.unchanged([before], [copy.deepcopy(before), self.candidate('2')]))
        after = copy.deepcopy(before)
        after['security']['sqn'] = {'$numberLong': '99'}
        self.assertFalse(sync.unchanged([before], [after]))

    def test_readback_keeps_sqn_bson_type(self):
        candidate = self.candidate()
        saved = copy.deepcopy(candidate)
        saved['schema_version'] = {'$numberInt': '1'}
        self.assertEqual(sync.normalize_int32(saved), candidate)
        saved['security']['sqn'] = {'$numberInt': '0'}
        self.assertNotEqual(sync.normalize_int32(saved), candidate)

    def source_output(self, **overrides):
        material = {'imsi': '460030000000001', 'ki': '00' * 16, 'opc': '11' * 16,
                    'amf': '8000', 'method': '5G_AKA', 'algorithm': 'milenage', 'access': 1, 'data': 1}
        return json.dumps({**material, **overrides})

    def test_source_is_read_only_and_excludes_sqn(self):
        info = [{'Config': {'Labels': {'com.docker.compose.project': 'oai-only-cn5g'}},
                 'State': {'Running': True}}]
        with patch.object(sync, 'run', side_effect=[json.dumps(info), self.source_output()]) as call:
            self.assertEqual(sync.source(), [self.candidate()])
        sql = call.call_args.args[1]
        self.assertIn('START TRANSACTION READ ONLY', sql)
        self.assertNotIn('sequenceNumber', sql)
        self.assertNotIn('UPDATE', sql)

    def test_incomplete_source_is_rejected(self):
        info = [{'Config': {'Labels': {'com.docker.compose.project': 'oai-only-cn5g'}},
                 'State': {'Running': True}}]
        for change in ({'data': 0}, {'access': 2}, {'method': 'unsupported'}, {'ki': 'invalid'}):
            with self.subTest(change=change), patch.object(sync, 'run', side_effect=[json.dumps(info), self.source_output(**change)]):
                with self.assertRaises((sync.Refused, ValueError)):
                    sync.source()

    def test_wrong_source_owner_is_rejected_before_query(self):
        info = [{'Config': {'Labels': {'com.docker.compose.project': 'other'}}, 'State': {'Running': True}}]
        with patch.object(sync, 'run', return_value=json.dumps(info)) as call:
            with self.assertRaises(sync.Refused):
                sync.source()
        self.assertEqual(call.call_count, 1)

    def test_private_backup_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.json'
            sync.private_json(path, {'private': True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                sync.private_json(path, {})

    def test_running_core_prevents_maintenance(self):
        with patch.object(sync, 'run', return_value='ActiveState=active\nMainPID=0\nControlPID=0\n'):
            with self.assertRaises(sync.Refused):
                sync.stopped()

    def test_command_errors_do_not_export_secrets(self):
        result = sync.subprocess.CompletedProcess([], 1, 'private-key', 'database-password')
        with patch.object(sync.subprocess, 'run', return_value=result):
            with self.assertRaises(sync.Refused) as caught:
                sync.run(['false'])
        self.assertNotIn('private-key', str(caught.exception))
        self.assertNotIn('database-password', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
