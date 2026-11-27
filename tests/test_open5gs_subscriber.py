import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v2_subscriber', ROOT / 'stacks/open5gs/subscriber.py')
subscriber = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subscriber)


class SubscriberTests(unittest.TestCase):
    def material(self):
        return dict(imsi='460030000000001', ki='00' * 16, opc='11' * 16, amf='8000', sqn='ffffffffffff')

    def test_old_sqn_is_not_copied_and_only_data_pdu_is_built(self):
        doc = subscriber.document(self.material())
        self.assertEqual(doc['security']['sqn'], {'$numberLong': '0'})
        self.assertEqual(doc['slice'][0]['session'][0]['name'], 'oai')
        self.assertEqual(doc['slice'][0]['session'][0]['type'], 1)
        self.assertEqual(doc['slice'][0]['session'][0]['qos']['index'], 9)
        self.assertEqual(doc['ambr'], {'uplink': {'value': 500, 'unit': 2}, 'downlink': {'value': 1000, 'unit': 2}})
        self.assertEqual(doc['slice'][0]['session'][0]['ambr'], doc['ambr'])
        self.assertNotIn('sd', doc['slice'][0])
        self.assertEqual(len(doc['slice'][0]['session']), 1)

    def test_no_old_sqn_is_required(self):
        material = self.material()
        del material['sqn']
        self.assertEqual(subscriber.document(material)['security']['sqn'], {'$numberLong': '0'})

    def test_input_refuses_wrong_identity_or_extra_fields(self):
        for change in ({'imsi': '001010000000001'}, {'ki': 'bad'}, {'other_subscriber': {}}, {'sqn': 1}):
            material = {**self.material(), **change}
            with self.assertRaises(ValueError):
                subscriber.document(material)

    def test_secret_files_refuse_symlinks_and_public_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'private.json'
            path.write_text('{}')
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                subscriber.read_private(path)
            path.chmod(0o600)
            self.assertEqual(subscriber.read_private(path), {})
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                subscriber.read_private(link)

    def test_import_has_unique_insert_no_upsert_or_sqn_update(self):
        script = subscriber.insert_script(subscriber.document(self.material()))
        self.assertIn('unique: true', script)
        self.assertIn('insertOne(candidate)', script)
        self.assertIn('already_exists', script)
        self.assertNotIn('updateOne', script)
        self.assertNotIn('upsert', script)
        self.assertIn('core.auth', script)
        self.assertIn('{relaxed: false}', script)
        self.assertIn("saved.security.sqn._bsontype !== 'Long'", script)
        self.assertNotIn('console.error', script)


if __name__ == '__main__':
    unittest.main()
