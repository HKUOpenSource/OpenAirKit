import json
import unittest

from aoc_spark.open5gs import Open5GS, parse_info, parse_prometheus, subscriber_id


AMF = {"items": [{"supi": "imsi-460030000000001", "suci": "private-suci", "pei": "private-imei",
                   "guti": "private-guti", "cm_state": "connected", "mm_state": "registered",
                   "gnb": {"amf_ue_ngap_id": 2, "ran_ue_ngap_id": 0, "gnb_id": 411, "cell_id": 0}}],
       "pager": {"count": 1}}
PDU = {"items": [{"supi": "imsi-460030000000001", "ue_activity": "active", "pdu": [{
    "psi": 1, "dnn": "oai", "ipv4": "10.0.0.31", "snssai": {"sst": 1, "sd": "ffffff"},
    "qos_flows": [{"qfi": 1, "5qi": 9}], "pdu_state": "active",
    "n3": {"gnb": {"teid": 1, "addr": "[172.28.81.1]:2152"},
            "upf": {"teid": 1437, "addr": "[172.28.81.14]:2152", "pdr_id": 2}}}]}],
       "pager": {"count": 1}}
GNB = {"items": [{"gnb_id": 411, "plmn": "46003", "ng": {"setup_success": True},
                   "num_connected_ues": 1}], "pager": {"count": 1}}


class Open5GSTests(unittest.TestCase):
    def test_info_exposes_numeric_identity_and_retains_allowlist(self):
        devices, observations, gnb = parse_info(AMF, PDU, GNB, '2026-09-12T12:00:00+00:00', 'amf-smf-run-a')
        self.assertEqual(len(devices), 1)
        device = devices[0]
        self.assertEqual(device['id'], subscriber_id('imsi-460030000000001'))
        self.assertEqual(device['identity'], AMF['items'][0]['supi'].removeprefix('imsi-'))
        self.assertEqual(device['registration'], 'registered')
        self.assertEqual(device['state'], 'registered')
        self.assertEqual(device['epoch'], 'amf-smf-run-a')
        self.assertEqual(device['correlation'], 'amf_smf_supi')
        self.assertEqual(device['sessions'][0]['address'], '10.0.0.31')
        self.assertEqual(device['sessions'][0]['five_qi'], 9)
        self.assertEqual(device['sessions'][0]['qfi'], 1)
        self.assertTrue(device['sessions'][0]['n3_verified'])
        encoded = json.dumps([devices, observations, gnb])
        for secret in ('private-suci', 'private-imei', 'private-guti', '1437', 'pdr_id'):
            self.assertNotIn(secret, encoded)
        metrics = {(item['entity'], item['name']): item['value'] for item in observations}
        self.assertEqual(metrics[('ocudu:oai', 'active_pdu_count')], 1)
        self.assertEqual(metrics[('ocudu:oai', 'observed_5qi')], 9)
        self.assertEqual(metrics[('ocudu:n3', 'active_session_paths')], 1)
        self.assertEqual(metrics[('ocudu', 'amf_connected_ue_count')], 1)

    def test_smf_only_identity_preserves_leading_zeroes(self):
        pdu = json.loads(json.dumps(PDU))
        pdu['items'][0]['supi'] = 'imsi-' + '00101' + '0' * 9 + '1'
        devices, _, _ = parse_info({'items': []}, pdu, GNB)
        self.assertEqual(devices[0]['identity'], pdu['items'][0]['supi'][5:])
        self.assertEqual(devices[0]['correlation'], 'smf_supi_only')
        self.assertEqual(devices[0]['registration'], 'unknown')

    def test_invalid_pool_other_dnn_and_unknown_identity_do_not_leak(self):
        pdu = json.loads(json.dumps(PDU))
        pdu['items'][0]['pdu'][0]['ipv4'] = '192.168.1.1'
        pdu['items'][0]['pdu'].append({'psi': 2, 'dnn': 'ims', 'ipv4': '10.0.9.2'})
        pdu['items'].append({'supi': 'invalid-secret', 'pdu': []})
        devices, observations, _ = parse_info(AMF, pdu, GNB)
        self.assertEqual(len(devices[0]['sessions']), 1)
        self.assertIsNone(devices[0]['sessions'][0]['address'])
        self.assertFalse(devices[0]['sessions'][0]['pool_valid'])
        active = next(item for item in observations if item['name'] == 'active_pdu_count')
        self.assertEqual(active['value'], 0)
        self.assertNotIn('invalid-secret', json.dumps(devices))

    def test_prometheus_allowlist_and_label_aggregation(self):
        raw = '''# HELP ignored ignored\ngnb 1\nran_ue 1\nfivegs_amffunction_rm_registeredsubnbr{plmnid="46003",snssai="1"} 1\nprocess_open_fds 999\n'''
        metrics = {item['name']: item['value'] for item in parse_prometheus(raw, 'amf')}
        self.assertEqual(metrics, {'gnbs': 1.0, 'ran_ues': 1.0, 'registered_subscribers': 1.0})

    def test_duplicate_supi_is_rejected_and_ngap_collision_is_not_merged(self):
        duplicate = {'items': AMF['items'] * 2, 'pager': {'count': 2}}
        devices, _, _ = parse_info(duplicate, PDU, GNB)
        self.assertEqual(devices, [])
        amf = json.loads(json.dumps(AMF))
        second = json.loads(json.dumps(AMF['items'][0]))
        second['supi'] = 'imsi-460030000000002'
        amf['items'].append(second); amf['pager']['count'] = 2
        devices, _, _ = parse_info(amf, PDU, GNB)
        self.assertEqual(len(devices), 2)
        self.assertTrue(all(device['identifiers'] == {} for device in devices))
        self.assertTrue(all(device['correlation'] == 'ambiguous_ngap_identifiers' for device in devices))

    def test_partial_failure_is_unavailable_not_zero(self):
        responses = {
            key: json.dumps(value) for key, value in {'amf_ue': AMF, 'smf_pdu': PDU, 'amf_gnb': GNB}.items()
        }
        from aoc_spark.open5gs import ENDPOINTS
        reverse = {url: name for name, url in ENDPOINTS.items()}
        def get(url):
            name = reverse[url]
            if name.endswith('metrics'):
                raise OSError('offline')
            return responses[name]
        result = Open5GS(get).collect()
        unavailable = [item for item in result['observations'] if item['name'] == 'metrics_available']
        self.assertEqual(len(unavailable), 3)
        self.assertTrue(all(item['status'] == 'unavailable' and item['value'] is None for item in unavailable))


if __name__ == '__main__':
    unittest.main()
