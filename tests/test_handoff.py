import subprocess
import unittest
from pathlib import Path
import json
from contextlib import ExitStack, nullcontext
import tempfile
from unittest.mock import patch

from scripts.repair_legacy_iperf import BAD, patched
from scripts.aoclib.radio import PROFILE, gnb_config, validate_profile
from scripts.radio_runtime import connection_evidence, HandoffFailure, start
from scripts import radio_runtime as runtime


CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config/spark.example.json").read_text())


class RadioTests(unittest.TestCase):
    def test_review_does_not_imply_device_or_rf_acceptance(self):
        validate_profile(PROFILE, serial_required=False)
        with self.assertRaises(ValueError):
            validate_profile(PROFILE)
        self.assertIs(PROFILE["rf_accepted"], False)

    def test_fixed_carrier_gain_and_serial(self):
        profile = dict(PROFILE, serial="AOCPARSEONLY")
        config = gnb_config(CONFIG, profile)
        self.assertEqual(config["cell_cfg"]["dl_arfcn"], 643392)
        self.assertIn("serial=AOCPARSEONLY,", config["ru_sdr"]["device_args"])
        for change in ({"tx_gain": 89.75}, {"serial": "a,b"}, {"reviewed": False}):
            with self.assertRaises(ValueError):
                gnb_config(CONFIG, dict(profile, **change))

    def test_sctp_requires_own_pid_exact_local_and_peer(self):
        line = 'ESTAB 0 0 172.28.80.1:35000 172.28.80.12:38412 users:(("gnb",pid=123,fd=8))'
        self.assertTrue(connection_evidence(line, 123, CONFIG))
        self.assertTrue(connection_evidence(line.replace("172.28.80.1:", "172.28.80.1%aoc-cn5g:"), 123, CONFIG))
        for bad in (line.replace("pid=123,", "pid=1234,"), line.replace("ESTAB", "LISTEN"),
                    line.replace("172.28.80.12", "192.168.70.132"), line.replace("172.28.80.1:", "172.28.80.11:")):
            self.assertFalse(connection_evidence(bad, 123, CONFIG))

    def exercise_start_failure(self, cleanup_fails):
        events = []
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            directory = Path(temporary)
            (directory / "core").mkdir()
            (directory / "radio.json").write_text(json.dumps(PROFILE))
            (directory / "core/bundle.json").write_text('{"subscribers_provisioned":true}')
            stack.enter_context(patch.object(runtime, "CONFIG", directory))
            stack.enter_context(patch.object(runtime, "switch_lock", return_value=nullcontext()))
            stack.enter_context(patch.object(runtime, "show", return_value={"ActiveState": "inactive", "SubState": "running"}))
            for name, value in (("record", None), ("inventory", {}), ("inspect", []), ("core_ready", None),
                                ("core_command", ["docker", "compose", "aoc-cn5g"]), ("discover", None)):
                stack.enter_context(patch.object(runtime, name, return_value=value))
            def command(argv, **kwargs):
                events.append(argv)
                if argv[:3] == ["systemctl", "start", "aoc-stack.target"]:
                    raise RuntimeError("startup failure")
                if cleanup_fails and argv[:3] == ["systemctl", "stop", "aoc-stack.target"]:
                    raise RuntimeError("cleanup failed")
            stack.enter_context(patch.object(runtime, "command", side_effect=command))
            stack.enter_context(patch.object(runtime, "usb_free", side_effect=lambda: events.append(["usb-free"])))
            with self.assertRaises(RuntimeError) as error:
                runtime.start(CONFIG)
            self.assertEqual(isinstance(error.exception, HandoffFailure), not cleanup_fails)
        self.assertLess(events.index(["systemctl", "stop", "oai-gnb.service"]), events.index(["usb-free"]))
        self.assertLess(events.index(["usb-free"]), events.index(["systemctl", "start", "aoc-stack.target"]))
        return events

    def test_failed_start_releases_device_before_allowing_recovery(self):
        events = self.exercise_start_failure(False)
        self.assertEqual(events[-1], ["usb-free"])

    def test_uncertain_cleanup_does_not_authorize_legacy_restart(self):
        events = self.exercise_start_failure(True)
        self.assertEqual(events[-1], ["systemctl", "stop", "aoc-stack.target"])

    def test_radio_start_with_monitor_running_uses_real_scoped_preflight(self):
        captured = {"architecture": "aarch64", "routes": {"ok": True, "data": []},
                    "addresses": {"ok": True, "data": []}, "networks": {"ok": True, "data": []},
                    "listeners": {"ok": True, "data": "tcp LISTEN 0 2048 127.0.0.1:8877 0.0.0.0:*\n"},
                    "units": {"ok": True, "data": ""}}
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            directory = Path(temporary)
            (directory / "core").mkdir()
            (directory / "radio.json").write_text(json.dumps(PROFILE))
            (directory / "core/bundle.json").write_text('{"subscribers_provisioned":true}')
            stack.enter_context(patch.object(runtime, "CONFIG", directory))
            stack.enter_context(patch.object(runtime, "switch_lock", return_value=nullcontext()))
            stack.enter_context(patch.object(runtime, "show", return_value={"ActiveState": "inactive", "SubState": "running"}))
            stack.enter_context(patch.object(runtime, "inventory", return_value=captured))
            for name in ("record", "core_ready", "usb_free", "discover"):
                stack.enter_context(patch.object(runtime, name))
            stack.enter_context(patch.object(runtime, "core_command", return_value=["docker", "compose"]))
            command = stack.enter_context(patch.object(runtime, "command"))
            runtime.start(CONFIG)
            command.assert_any_call(["systemctl", "start", "aoc-stack.target"], timeout=200)


class LegacyRepairTests(unittest.TestCase):
    def test_quoting_preserves_awk_program_without_outer_expansion(self):
        source = ('set -u\ncapture() { printf "%s" "$4"; }\n'
                  "capture fake /bin/sh -ec '\nfor pid in $(ps | " + BAD + "); do :; done\n'\n")
        before = subprocess.run(["bash"], input=source, text=True, capture_output=True)
        after = subprocess.run(["bash"], input=patched(source), text=True, capture_output=True)
        self.assertNotEqual(before.returncode, 0)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertIn(BAD, after.stdout)

    def test_repair_rejects_unexpected_source(self):
        with self.assertRaises(ValueError):
            patched("#!/bin/sh\nexit 0\n")
