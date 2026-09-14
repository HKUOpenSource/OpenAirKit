import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.aoclib.subscriber import add, sql_text, statements, validate_material


ROOT = Path(__file__).resolve().parents[1]


class SubscriberTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/spark.example.json").read_text())
        self.material = {"imsi": "001010000000001", "ki": "0" * 32, "opc": "1" * 32,
                         "sqn": "0" * 12, "amf": "8000"}

    def test_invalid_material_is_rejected_without_echoing_secret(self):
        self.material["ki"] = "sensitive-invalid-value"
        with self.assertRaises(ValueError) as caught:
            validate_material(self.material)
        self.assertNotIn(self.material["ki"], str(caught.exception))

    def test_insert_only_transaction_cannot_reset_existing_sqn(self):
        sql = statements(self.config, self.material)
        self.assertTrue(sql.startswith("START TRANSACTION;"))
        self.assertTrue(sql.endswith("COMMIT;\n"))
        self.assertEqual(sql.count("INSERT INTO"), 3)
        for forbidden in ("UPDATE", "DELETE", "REPLACE", "DUPLICATE KEY"):
            self.assertNotIn(forbidden, sql)

    def test_sql_encoding_has_no_user_controlled_sql_characters(self):
        encoded = sql_text("'\\; DROP TABLE x; --")
        self.assertRegex(encoded, r"^CONVERT\(0x[0-9a-f]+ USING utf8mb4\)$")

    @patch("scripts.aoclib.subscriber.subprocess.run")
    def test_refuses_group_readable_credentials(self, run):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sim.json"
            source.write_text(json.dumps(self.material))
            source.chmod(0o640)
            with self.assertRaisesRegex(ValueError, "private"):
                add(self.config, Path(temporary), source, [])
        run.assert_not_called()

    @patch("scripts.aoclib.subscriber.subprocess.run")
    def test_database_errors_do_not_expose_secret_values(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", self.material["ki"])
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sim.json"
            source.write_text(json.dumps(self.material))
            source.chmod(0o600)
            with self.assertRaises(ValueError) as caught:
                add(self.config, Path(temporary), source, ["docker", "compose"])
        self.assertNotIn(self.material["ki"], str(caught.exception))
        self.assertNotIn(self.material["ki"], " ".join(run.call_args.args[0]))
