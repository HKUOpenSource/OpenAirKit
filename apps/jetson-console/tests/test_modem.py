import unittest

from aoc_jetson.modem import (active, address, context_address, contexts, registration,
                                  select_data, serving_cell)


DATA = {"dnn": "oai", "pdu_type": "IP", "ue_pool": "10.0.0.0/24",
        "qos_5qi": 9, "cid_min": 1, "cid_max": 16}


class ModemParserTests(unittest.TestCase):
    def test_all_context_ids_are_preserved_but_only_data_range_is_selected(self):
        current = contexts(['+CGDCONT: 0,"IP","vendor"', '+CGDCONT: 1,"IP","oai"',
                            '+CGDCONT: 2,"IPV4V6","ims"', '+CGDCONT: 3,"IPV4V6","sos"',
                            '+CGDCONT: 22,"IPV4V6",""', '+CGDCONT: 23,"IPV4V6",""',
                            '+CGDCONT: 24,"IPV4V6",""', '+CGDCONT: 255,"IP","vendor255"'])
        self.assertEqual(set(current), {0, 1, 2, 3, 22, 23, 24, 255})
        self.assertEqual(select_data(current, DATA), (1, False))

    def test_duplicate_and_reserved_data_dnn_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate data"):
            select_data({1: {"dnn": "oai"}, 2: {"dnn": "oai"}}, DATA)
        with self.assertRaisesRegex(ValueError, "reserved"):
            select_data({22: {"dnn": "oai"}}, DATA)

    def test_free_data_context_does_not_overwrite_existing_contexts(self):
        self.assertEqual(select_data({1: {"dnn": "ims"}, 2: {"dnn": "sos"}}, DATA), (3, True))

    def test_c5greg_is_authoritative_and_disagreement_is_visible(self):
        result = registration(["+C5GREG: 0,1", "OK"], ["+CEREG: 0,0", "OK"])
        self.assertTrue(result["registered_5gs"])
        self.assertTrue(result["disagrees_with_cereg"])
        self.assertEqual(result["source"], "AT+C5GREG")

    def test_address_sources_require_expected_pool(self):
        self.assertEqual(address(['+CGPADDR: 1,"10.0.0.8"', "OK"], 1, "10.0.0.0/24"), "10.0.0.8")
        self.assertIsNone(address(['+CGPADDR: 1,"10.80.0.8"', "OK"], 1, "10.0.0.0/24"))
        self.assertEqual(context_address(['+CGCONTRDP: 1,0,"oai","10.0.0.9"', "OK"], 1, "oai", "10.0.0.0/24"), "10.0.0.9")

    def test_radio_ssb_is_observation_not_carrier_configuration(self):
        cell = serving_cell(['+QENG: "servingcell","NOCONN","NR5G-SA","TDD",460,03,00066C000,666,1,643104,78,3,-85,-10,35,1,-'])
        self.assertEqual(cell["ssb_arfcn"], 643104)
        self.assertEqual(cell["rsrp_dbm"], -85)
        self.assertNotIn("carrier_arfcn", cell)

    def test_active_contexts_are_parsed_strictly(self):
        self.assertEqual(active(["+CGACT: 1,1", "+CGACT: 2,0", "+CGACT: 255,1"]), {1, 255})


if __name__ == "__main__":
    unittest.main()
