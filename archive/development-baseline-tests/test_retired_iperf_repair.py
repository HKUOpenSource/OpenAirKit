import subprocess
import unittest
from scripts.repair_legacy_iperf import BAD, patched


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
