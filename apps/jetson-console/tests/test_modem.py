import unittest
from unittest.mock import Mock

from aoc_jetson.modem import (Modem, active, address, context_address, contexts, registration,
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


class ModemPowerTests(unittest.TestCase):
    def setUp(self):
        self.modem = Modem({"commissioned": True, "sim_sha256": "0" * 64,
                            "network": {"data": DATA}})
        self.functionality = 1
        self.failures = set()
        self.commands = []
        self.modem.fingerprint = Mock(side_effect=self.fingerprint)
        self.modem.exchange = self.exchange

    def fingerprint(self):
        if self.functionality == 0:
            raise ValueError("SIM unavailable while powered down")
        return "0" * 64, "Synthetic SIM"

    def exchange(self, command, timeout=3, optional=False):
        self.commands.append(command)
        if command in ("AT+CFUN=0", "AT+CFUN=1"):
            self.functionality = int(command[-1])
            if command in self.failures:
                raise TimeoutError("Lost acknowledgement for " + command)
        elif command == "AT+CFUN?":
            if "readback" + str(self.functionality) in self.failures:
                raise TimeoutError("Lost power readback")
            return ["+CFUN: " + str(self.functionality), "OK"]
        return ["OK"]

    def test_uncertain_power_off_restores_once_and_preserves_failure(self):
        for failure in ("AT+CFUN=0", "readback0"):
            with self.subTest(failure=failure):
                self.setUp()
                self.failures.add(failure)
                with self.assertRaises(TimeoutError):
                    self.modem.write("cfun0")
                self.assertEqual(self.functionality, 1)
                self.assertEqual([c for c in self.commands if "=" in c],
                                 ["AT+CFUN=0", "AT+CFUN=1"])
                self.assertFalse(self.modem.power_restore_authorized)
                self.modem.fingerprint.assert_called_once()

    def test_failed_compensation_is_bounded_and_revokes_authorization(self):
        self.failures.update({"readback0", "readback1"})
        with self.assertRaisesRegex(RuntimeError, "power restoration failed"):
            self.modem.write("cfun0")
        self.assertEqual(self.commands.count("AT+CFUN=1"), 1)
        self.assertFalse(self.modem.power_restore_authorized)
        self.modem.fingerprint.side_effect = ValueError("SIM identity mismatch")
        with self.assertRaisesRegex(ValueError, "SIM identity mismatch"):
            self.modem.write("cfun1")
        self.assertEqual(self.commands.count("AT+CFUN=1"), 1)

    def test_successful_power_cycle_does_not_query_disabled_sim(self):
        self.modem.write("cfun0")
        self.modem.write("cfun1")
        self.assertEqual(self.functionality, 1)
        self.modem.fingerprint.assert_called_once()
        self.assertFalse(self.modem.power_restore_authorized)

    def test_failed_normal_power_on_does_not_leave_identity_bypass(self):
        self.modem.write("cfun0")
        self.failures.add("readback1")
        with self.assertRaises(TimeoutError):
            self.modem.write("cfun1")
        self.assertFalse(self.modem.power_restore_authorized)
        self.assertEqual(self.commands.count("AT+CFUN=1"), 1)

    def test_rejected_identity_does_not_authorize_or_attempt_power_restore(self):
        self.modem.fingerprint.side_effect = None
        self.modem.fingerprint.return_value = ("1" * 64, "Different synthetic SIM")
        with self.assertRaisesRegex(ValueError, "SIM identity mismatch"):
            self.modem.write("cfun0")
        self.assertEqual(self.commands, [])
        self.assertFalse(self.modem.power_restore_authorized)


if __name__ == "__main__":
    unittest.main()
