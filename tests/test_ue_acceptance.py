import json
from contextlib import nullcontext
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import ue_acceptance as ue


def context(cid, dnn):
    return '+CGDCONT: {},"IP","{}","0.0.0.0",0,0'.format(cid, dnn)


class UeTests(unittest.TestCase):
    def test_interface_follows_at_usb_parent_and_rejects_ambiguity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            net, tty = root / "net", root / "tty"
            net.mkdir(); tty.mkdir()
            port = root / "ttyUSB2"; port.touch()
            driver = root / "cdc_ether"; driver.mkdir()
            modem = root / "usb-modem"; modem.mkdir()
            other = root / "usb-other"; other.mkdir()
            for device in (modem, other):
                (device / "idVendor").write_text("2c7c")
                (device / "idProduct").write_text("0801")
            at = modem / "if02"; at.mkdir()
            (tty / "ttyUSB2").mkdir()
            (tty / "ttyUSB2/device").symlink_to(at, target_is_directory=True)
            def interface(name, device):
                usb = device / name; usb.mkdir()
                (usb / "driver").symlink_to(driver, target_is_directory=True)
                (net / name).mkdir()
                (net / name / "device").symlink_to(usb, target_is_directory=True)
            interface("enx-renamed", modem)
            interface("enx-unrelated", other)
            (net / "wlan0").mkdir()
            with patch.object(ue, "SYS_NET", net), patch.object(ue, "SYS_TTY", tty), patch.object(ue, "PORT", port):
                self.assertEqual(ue.data_interface(), "enx-renamed")
                (net / "enx-renamed").rename(net / "enx-after-reset")
                self.assertEqual(ue.data_interface(), "enx-after-reset")
                interface("enx-duplicate", modem)
                with self.assertRaisesRegex(ValueError, "found 2"):
                    ue.data_interface()
                (modem / "idVendor").write_text("ffff")
                with self.assertRaisesRegex(ValueError, "reviewed RM520N"):
                    ue.data_interface()

    def test_missing_at_port_never_falls_back_to_a_host_interface(self):
        with patch.object(ue, "PORT", Path('/nonexistent-aoc-test-port')):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                ue.data_interface()

    def test_cid_selected_by_dnn_not_fixed_number(self):
        current = ue.contexts([context(3, "oai"), context(1, "ims"), "OK"])
        self.assertEqual(ue.select_cids(current), (3, 1, False))

    def test_new_ims_uses_unused_cid_without_overwriting_others(self):
        current = ue.contexts([context(1, "oai"), context(2, "enterprise"), context(3, "other")])
        self.assertEqual(ue.select_cids(current), (1, 4, True))

    def test_reserved_and_vendor_contexts_are_preserved_without_becoming_candidates(self):
        current = ue.contexts([context(0, ""), context(1, "oai"), context(17, "vendor")])
        self.assertEqual(set(current), {0, 1, 17})
        self.assertEqual(ue.select_cids(current), (1, 2, True))
        with self.assertRaises(ValueError):
            ue.select_cids(ue.contexts([context(0, "oai"), context(2, "ims")]))

    def test_duplicate_cid_rejected_even_when_dnn_matches(self):
        with self.assertRaises(ValueError):
            ue.contexts([context(1, "oai"), context(1, "oai")])

    def test_ambiguous_or_full_context_table_rejected(self):
        for lines in ([context(1, "oai"), context(2, "oai")], [context(1, "ims")],
                      [context(cid, "oai" if cid == 1 else "other") for cid in range(1, 17)]):
            with self.assertRaises(ValueError):
                ue.select_cids(ue.contexts(lines))

    def test_addresses_and_registration_cannot_match_other_context_or_wifi(self):
        lines = ['+CGPADDR: 1,"10.80.0.2"', '+CGPADDR: 2,"10.80.9.2"']
        self.assertEqual(ue.pdu_ip(lines, 2, "10.80.9.0/24"), "10.80.9.2")
        for cid, pool in ((1, "10.80.9.0/24"), (2, "10.0.9.0/24")):
            with self.assertRaises(ValueError):
                ue.pdu_ip(lines, cid, pool)
        self.assertTrue(ue.registered(["+C5GREG: 2,1", "OK"]))
        self.assertFalse(ue.registered(["+C5GREG: 2,11", "OK"]))
        self.assertFalse(ue.registered(["+CEREG: 2,1", "OK"]))

    def test_busy_original_console_rejected(self):
        connection = sqlite3.connect(":memory:")
        for sql in ("CREATE TABLE operation_lock(slot,kind)", "CREATE TABLE jobs(state)", "CREATE TABLE speed_tests(state)"):
            connection.execute(sql)
        ue.idle(connection)
        connection.execute("INSERT INTO operation_lock VALUES(1,'recovery')")
        with self.assertRaises(ValueError):
            ue.idle(connection)
        connection.execute("DELETE FROM operation_lock")
        connection.execute("INSERT INTO speed_tests VALUES('running')")
        with self.assertRaises(ValueError):
            ue.idle(connection)
        connection.close()

    def test_route_failure_removes_only_new_host_route(self):
        addresses = json.dumps([{"addr_info": [{"scope": "global", "local": "192.168.225.88"}]}])
        with patch.object(ue, "data_interface", return_value="enx-new"), patch.object(ue, "run", side_effect=[addresses, "[]", "", json.dumps([{"dev": "wlan0"}]), ""]) as run:
            with self.assertRaises(ValueError):
                with ue.data_route("ocudu"):
                    self.fail("Wi-Fi path must never reach a test")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[-1], ["ip", "route", "del", "172.28.80.15/32", "via", "192.168.225.1",
                                        "dev", "enx-new", "proto", "186"])
        self.assertFalse(any("default" in command or "replace" in command for command in commands))

    def test_conflicting_host_route_is_not_replaced(self):
        addresses = json.dumps([{"addr_info": [{"scope": "global", "local": "192.168.225.88"}]}])
        with patch.object(ue, "data_interface", return_value="enx-new"), patch.object(ue, "run", side_effect=[addresses, json.dumps([{"dev": "wlan0"}])]) as run:
            with self.assertRaises(ValueError):
                with ue.data_route("ocudu"):
                    self.fail("Conflicting route must be preserved")
        self.assertEqual(run.call_count, 2)

    def test_at_queries_allow_known_lowercase_but_not_arbitrary_commands(self):
        modem = ue.Modem()
        modem.serial = Mock()
        modem.serial.readline.return_value = b"OK\r\n"
        modem.query('AT+QENG="servingcell"')
        for command in ("AT+CFUN=1,1", 'AT+CGDCONT=1,"IP","oai"', "AT\rAT+CFUN=0", "AT+QPOWD"):
            with self.assertRaises(ValueError):
                modem.query(command)
        self.assertEqual(modem.serial.write.call_count, 1)

    def test_stop_waits_then_signals_only_original_web_main_process(self):
        checks = 0
        def command(argv, **kwargs):
            nonlocal checks
            if "ActiveState" in argv:
                checks += 1
                return "deactivating" if checks <= 16 else "inactive"
            if "ExecStart" in argv:
                return "/opt/oai-console/venv/bin/python -m uvicorn oai_console.main:app"
            return ""
        with patch.object(ue, "run", side_effect=command) as run, patch.object(ue, "maintenance_required") as ready, \
                patch.object(ue.time, "sleep"):
            ue.stop_console()
        self.assertEqual(ready.call_count, 2)
        signals = [call.args[0] for call in run.call_args_list if "kill" in call.args[0]]
        self.assertEqual(signals, [["systemctl", "kill", "--kill-who=main", "--signal=SIGINT", "oai-console.service"]])

    def test_stop_does_not_signal_changed_service_executable(self):
        def command(argv, **kwargs):
            return "deactivating" if "ActiveState" in argv else "unexpected"
        with patch.object(ue, "run", side_effect=command) as run, patch.object(ue, "maintenance_required"), \
                patch.object(ue.time, "sleep"):
            with self.assertRaises(ValueError):
                ue.stop_console()
        self.assertFalse(any("kill" in call.args[0] for call in run.call_args_list))

    def test_diagnose_only_queries_state_and_omits_sim_identity(self):
        modem = Mock()
        modem.query.side_effect = lambda command, **kwargs: [context(0, ""), context(1, "oai"), context(2, "ims")] if command == "AT+CGDCONT?" else ["OK"]
        with patch.object(ue, "save"):
            result = ue.diagnose(modem)
        commands = [call.args[0] for call in modem.query.call_args_list]
        self.assertNotIn("AT+CIMI", commands)
        self.assertFalse(any(command in ("AT+CFUN=0", "AT+CFUN=1") or command.startswith("AT+CGACT=") for command in commands))
        self.assertIn("AT+CGPADDR=2", result["queries"])

    def test_connect_preserves_existing_sa_data_and_only_activates_ims(self):
        modem = Mock(identity_pending=False)
        values = {"AT+CGDCONT?": [context(1, "oai"), context(2, "ims")],
                  "AT+CGACT?": ["+CGACT: 1,1", "+CGACT: 2,0"],
                  "AT+CGPADDR=1": ['+CGPADDR: 1,"10.80.0.2"'], "AT+C5GREG?": ["+C5GREG: 0,1"],
                  "AT+CGACT=1,2": ["OK"]}
        modem.query.side_effect = lambda command, **kwargs: values[command]
        with patch.object(ue, "snapshot", return_value={"accepted": True}):
            self.assertEqual(ue.connect(modem, "ocudu"), {"accepted": True})
        commands = [call.args[0] for call in modem.query.call_args_list]
        self.assertNotIn("AT+CFUN=0", commands)
        self.assertNotIn("AT+CFUN=1", commands)
        self.assertNotIn("AT+CEREG?", commands)
        self.assertEqual([command for command in commands if command.startswith("AT+CGACT=")], ["AT+CGACT=1,2"])

    def test_cfun_error_requires_readback_before_proceeding(self):
        modem = Mock()
        modem.query.side_effect = [["ERROR"], ["+CFUN: 1", "OK"]]
        ue.set_functionality(modem, 1)
        self.assertEqual(modem.query.call_args_list[-1].args[0], "AT+CFUN?")
        modem.query.side_effect = lambda command, **kwargs: ["ERROR"] if command == "AT+CFUN=1" else ["+CFUN: 0", "OK"]
        with patch.object(ue.time, "sleep"), self.assertRaises(ValueError):
            ue.set_functionality(modem, 1)

    def test_explicit_reconnect_resets_once_despite_correct_data_and_saves_prior_state(self):
        modem = Mock(identity_pending=False)
        values = {"AT+CGDCONT?": [context(1, "oai"), context(2, "ims")],
                  "AT+CGACT?": ["+CGACT: 1,1", "+CGACT: 2,0"],
                  "AT+CGPADDR=1": ['+CGPADDR: 1,"10.80.0.2"'],
                  "AT+C5GREG?": ["+C5GREG: 0,1"], "AT+CGACT=1,2": ["OK"]}
        modem.query.side_effect = lambda command, **kwargs: values[command]
        with patch.object(ue, "save") as save, patch.object(ue, "set_functionality") as functionality, \
                patch.object(ue, "wait_registration") as registered, patch.object(ue.time, "sleep"), \
                patch.object(ue, "snapshot", return_value={"profile": "ocudu"}):
            def reset(modem, value):
                self.assertEqual(save.call_count, 1)
            functionality.side_effect = reset
            ue.connect(modem, "ocudu", reconnect=True)
        self.assertEqual([call.args[1] for call in functionality.call_args_list], [0, 1])
        registered.assert_called_once_with(modem)
        self.assertEqual(save.call_args.args[1]["active_cids"], [1])

    def test_explicit_reconnect_does_not_retry_after_a_reset_failure(self):
        modem = Mock(identity_pending=False)
        modem.query.side_effect = lambda command, **kwargs: (
            [context(1, "oai"), context(2, "ims")] if command == "AT+CGDCONT?" else ["OK"])
        with patch.object(ue, "save"), patch.object(ue, "set_functionality", side_effect=ValueError("reset failed")) as reset:
            with self.assertRaisesRegex(ValueError, "reset failed"):
                ue.connect(modem, "ocudu", reconnect=True)
        reset.assert_called_once_with(modem, 0)
        self.assertFalse(any(call.args[0].startswith("AT+CGACT=") for call in modem.query.call_args_list))

    def test_explicit_reconnect_refuses_unprepared_profile_before_reset(self):
        modem = Mock(identity_pending=False)
        modem.query.side_effect = lambda command, **kwargs: (
            [context(1, "oai"), context(2, "ims")] if command == "AT+CGDCONT?" else ["OK"])
        with patch.object(ue, "save") as save, patch.object(ue, "set_functionality") as reset:
            with self.assertRaisesRegex(ValueError, "Prepare the selected IMS context"):
                ue.connect(modem, "legacy", reconnect=True)
        save.assert_not_called()
        reset.assert_not_called()


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        for name, replacement in (
                ("snapshot", Mock(return_value={"profile": "ocudu", "data_ip": "10.80.0.2", "ims_ip": "10.80.9.2"})),
                ("data_route", Mock(side_effect=lambda profile: nullcontext(("172.28.80.15", "192.168.225.88", "enx-new")))),
                ("verify_data_route", Mock()),
                ("run", Mock(return_value="5 received, 0% packet loss")),
                ("save", Mock(side_effect=lambda name, value: self.records.append(json.loads(json.dumps(value)))))):
            handle = patch.object(ue, name, replacement)
            handle.start()
            self.addCleanup(handle.stop)
        self.sleep = Mock()
        handle = patch.object(ue.time, "sleep", self.sleep)
        handle.start()
        self.addCleanup(handle.stop)

    def completed(self, error=None):
        report = {"error": error} if error else {"end": {"sum_received": {"bytes": 3500000, "bits_per_second": 5400000}}}
        return subprocess.CompletedProcess([], 1 if error else 0, json.dumps(report), "")

    def test_downlink_failure_reports_json_cause_and_preserves_uplink(self):
        with patch.object(ue.subprocess, "run", side_effect=[self.completed(), self.completed("the server is busy running a test")]):
            with self.assertRaisesRegex(ValueError, "downlink.*server is busy"):
                ue.probe(Mock(), "ocudu")
        record = self.records[-1]
        self.assertFalse(record["passed"])
        self.assertEqual(record["uplink_bps"], 5400000)
        self.assertNotIn("downlink_bps", record)
        self.assertEqual(record["measurements"]["downlink"]["returncode"], 1)
        self.assertIn("server is busy", record["measurements"]["downlink"]["stdout"])
        self.sleep.assert_called_once_with(3)
        self.assertFalse(record["bidirectional_passed"])

    def test_success_requires_both_directions_bound_to_the_ue_source(self):
        with patch.object(ue.subprocess, "run", side_effect=[self.completed(), self.completed()]) as run:
            result = ue.probe(Mock(), "ocudu")
        self.assertTrue(result["passed"])
        self.assertEqual(result["phase"], "complete")
        for call in run.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[argv.index("-B") + 1], "192.168.225.88")
            self.assertEqual(argv[argv.index("-c") + 1], "172.28.80.15")
        self.assertIn("-R", run.call_args_list[1].args[0])
        self.sleep.assert_called_once_with(3)
        self.assertTrue(any(item["phase"] == "settling" and not item["passed"] for item in self.records))
        self.assertEqual(result["direction_settle_seconds"], 3)
        self.assertEqual(ue.verify_data_route.call_count, 4)

    def test_timeout_preserves_partial_output_without_claiming_success(self):
        error = subprocess.TimeoutExpired(["iperf3"], 20, output=b"partial JSON", stderr=b"interrupted")
        with patch.object(ue.subprocess, "run", side_effect=error):
            with self.assertRaisesRegex(TimeoutError, "uplink.*20 seconds"):
                ue.probe(Mock(), "ocudu")
        record = self.records[-1]
        self.assertFalse(record["passed"])
        self.assertEqual(record["measurements"]["uplink"]["stdout"], "partial JSON")
        self.assertTrue(record["measurements"]["uplink"]["timed_out"])

    def test_downlink_diagnostic_does_not_run_uplink_or_claim_bidirectional_pass(self):
        with patch.object(ue.subprocess, "run", return_value=self.completed()) as run:
            result = ue.probe(Mock(), "ocudu", "downlink")
        self.assertEqual(run.call_count, 1)
        self.assertIn("-R", run.call_args.args[0])
        self.assertTrue(result["passed"])
        self.assertFalse(result["bidirectional_passed"])
        self.assertEqual(result["directions"], ["downlink"])
        self.assertNotIn("uplink_bps", result)
        self.sleep.assert_not_called()

    def test_route_change_during_settle_prevents_second_measurement(self):
        ue.verify_data_route.side_effect = [None, None, ValueError("Probe would not use the UE data interface")]
        with patch.object(ue.subprocess, "run", return_value=self.completed()) as run:
            with self.assertRaisesRegex(ValueError, "UE data interface"):
                ue.probe(Mock(), "ocudu")
        self.assertEqual(run.call_count, 1)
        self.assertFalse(self.records[-1]["passed"])
        self.assertIn("uplink_bps", self.records[-1])

    def test_exit_zero_without_a_receiver_result_is_not_a_pass(self):
        for output in ("invalid JSON", "[]", '{"end":{"sum_received":{"bytes":1,"bits_per_second":0}}}'):
            with patch.object(ue.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                with self.assertRaisesRegex(ValueError, "no valid positive receiver result"):
                    ue.probe(Mock(), "ocudu")
            self.assertFalse(self.records[-1]["passed"])


class ImsTypeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        state_patch = patch.object(ue, "STATE", self.state)
        state_patch.start()
        self.addCleanup(state_patch.stop)
        self.original_lines = [context(1, "oai"),
                               '+CGDCONT: 2,"IPV4V6","ims","' + ".".join(["0"] * 16) + '",0,0',
                               context(23, ""), context(3, "sos")]
        self.lines = list(self.original_lines)
        self.active = {1}
        ue.save("baseline.json", {"responses": {"AT+CGDCONT?": self.original_lines}})
        self.modem = Mock()
        self.modem.query.side_effect = self.query

    def query(self, command, **kwargs):
        if command == "AT+CGDCONT?":
            return list(self.lines)
        if command == "AT+CGACT?":
            return ["+CGACT: {},1".format(cid) for cid in sorted(self.active)]
        if command == 'AT+CGDCONT=2,"IP","ims"':
            self.assertTrue((self.state / "modified-ims.json").exists())
            self.lines[1] = context(2, "ims")
            return ["OK"]
        if command == 'AT+CGDCONT=2,"IPV4V6","ims"':
            self.lines[1] = self.original_lines[1]
            return ["OK"]
        if command == "AT+CGACT=0,2":
            self.active.remove(2)
            return ["OK"]
        self.fail("Unexpected command: " + command)

    def test_inactive_ims_adjustment_is_backed_up_and_other_contexts_preserved(self):
        ue.ensure_ims_ipv4(self.modem)
        self.assertEqual(self.active, {1})
        self.assertEqual(self.lines[0], self.original_lines[0])
        self.assertEqual(self.lines[2:], self.original_lines[2:])
        self.assertEqual(ue.contexts(self.lines)[2]["type"], "IP")
        saved = (self.state / "modified-ims.json").read_bytes()
        ue.ensure_ims_ipv4(self.modem)
        self.assertEqual((self.state / "modified-ims.json").read_bytes(), saved)

    def test_active_ims_type_is_never_overwritten(self):
        self.active.add(2)
        with self.assertRaisesRegex(ValueError, "IMS is active"):
            ue.ensure_ims_ipv4(self.modem)
        self.assertEqual(self.lines, self.original_lines)
        self.assertFalse((self.state / "modified-ims.json").exists())

    def test_changed_baseline_or_static_ims_address_prevents_write(self):
        for changed in (self.original_lines[1] + ",1", self.original_lines[1].replace("0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0", "10.0.9.9")):
            self.lines[1] = changed
            with self.assertRaises(ValueError):
                ue.ensure_ims_ipv4(self.modem)
        self.assertFalse((self.state / "modified-ims.json").exists())

    def test_unexpected_readback_keeps_backup_and_does_not_activate(self):
        def query(command, **kwargs):
            response = self.query(command, **kwargs)
            if command == 'AT+CGDCONT=2,"IP","ims"':
                self.lines[1] += ",1"
            return response
        self.modem.query.side_effect = query
        with self.assertRaisesRegex(ValueError, "readback"):
            ue.ensure_ims_ipv4(self.modem)
        self.assertTrue((self.state / "modified-ims.json").exists())
        self.assertEqual(self.active, {1})

    def test_restore_changes_only_owned_ims_and_retains_backup_until_full_recovery(self):
        ue.ensure_ims_ipv4(self.modem)
        self.active.add(2)
        ue.restore_ims_type(self.modem, ue.contexts(self.original_lines))
        self.assertEqual(self.lines, self.original_lines)
        self.assertEqual(self.active, {1})
        self.assertTrue((self.state / "modified-ims.json").exists())
        ue.restore_ims_type(self.modem, ue.contexts(self.original_lines))

    def test_restore_refuses_changed_ownership(self):
        ue.ensure_ims_ipv4(self.modem)
        self.lines[1] = context(2, "enterprise")
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            ue.restore_ims_type(self.modem, ue.contexts(self.original_lines))
        self.assertEqual(self.lines[1], context(2, "enterprise"))

    def test_failed_modem_write_keeps_original_recovery_record_for_retry(self):
        def query(command, **kwargs):
            if command == 'AT+CGDCONT=2,"IP","ims"':
                raise ValueError("Modem rejected write")
            return self.query(command, **kwargs)
        self.modem.query.side_effect = query
        with self.assertRaisesRegex(ValueError, "Modem rejected"):
            ue.ensure_ims_ipv4(self.modem)
        before = (self.state / "modified-ims.json").read_bytes()
        self.modem.query.side_effect = self.query
        ue.ensure_ims_ipv4(self.modem)
        self.assertEqual((self.state / "modified-ims.json").read_bytes(), before)

    def test_profile_round_trip_restores_legacy_type_and_preserves_original_backup(self):
        ue.ensure_ims_profile(self.modem, "ocudu")
        saved = (self.state / "modified-ims.json").read_bytes()
        ue.ensure_ims_profile(self.modem, "legacy")
        self.assertEqual(self.lines, self.original_lines)
        self.assertEqual(self.active, {1})
        ue.ensure_ims_profile(self.modem, "ocudu")
        self.assertEqual(ue.contexts(self.lines)[2]["type"], "IP")
        self.assertEqual((self.state / "modified-ims.json").read_bytes(), saved)
        self.assertEqual(self.active, {1})

    def test_legacy_profile_never_rewrites_active_ims_or_guesses_missing_backup(self):
        ue.ensure_ims_profile(self.modem, "ocudu")
        self.active.add(2)
        with self.assertRaisesRegex(ValueError, "IMS is active"):
            ue.ensure_ims_profile(self.modem, "legacy")
        self.active.remove(2)
        (self.state / "modified-ims.json").unlink()
        with self.assertRaisesRegex(ValueError, "no matching original recovery record"):
            ue.ensure_ims_profile(self.modem, "legacy")
        self.assertEqual(ue.contexts(self.lines)[2]["type"], "IP")

    def test_legacy_connect_restores_ims_type_before_activation_without_cfun_reset(self):
        ue.ensure_ims_profile(self.modem, "ocudu")
        self.modem.identity_pending = False
        def query(command, **kwargs):
            if command == "AT+CGPADDR=1":
                return ['+CGPADDR: 1,"10.0.0.2"']
            if command == "AT+C5GREG?":
                return ["+C5GREG: 0,1"]
            if command == "AT+CGACT=1,2":
                self.assertEqual(ue.contexts(self.lines)[2]["type"], "IPV4V6")
                self.active.add(2)
                return ["OK"]
            return self.query(command, **kwargs)
        self.modem.query.side_effect = query
        with patch.object(ue, "snapshot", return_value={"profile": "legacy"}):
            self.assertEqual(ue.connect(self.modem, "legacy"), {"profile": "legacy"})
        self.assertEqual(self.active, {1, 2})
        commands = [call.args[0] for call in self.modem.query.call_args_list]
        self.assertFalse(any(command.startswith("AT+CFUN=") for command in commands))
