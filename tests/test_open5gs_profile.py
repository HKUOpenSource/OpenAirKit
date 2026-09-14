import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("open5gs_config", ROOT / "stacks/open5gs/config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class Open5GSProfileTests(unittest.TestCase):
    def test_reviewed_single_data_profile_loads(self):
        self.assertEqual(config.load(ROOT / "config/network-profile.example.json")["data"]["qos_5qi"], 9)

    def test_ims_dnn_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            value = (ROOT / "config/network-profile.example.json").read_text().replace('"oai"', '"ims"', 1)
            path.write_text(value)
            with self.assertRaisesRegex(ValueError, "single IPv4 oai"):
                config.load(path)

    def test_wrong_pool_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            value = (ROOT / "config/network-profile.example.json").read_text().replace("10.0.0.0/24", "10.80.0.0/24")
            path.write_text(value)
            with self.assertRaisesRegex(ValueError, "UE pool"):
                config.load(path)

    def test_ims_fields_are_not_part_of_the_profile(self):
        value = config.load(ROOT / "config/network-profile.example.json")
        self.assertNotIn("ims", value["data"]["dnn"])
        self.assertNotIn("ims_dnn", value)


if __name__ == "__main__":
    unittest.main()
