import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import tarfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("open5gs_prepare", ROOT / "stacks/open5gs/build/prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
verify_spec = importlib.util.spec_from_file_location("open5gs_verify", ROOT / "stacks/open5gs/build/verify.py")
verify = importlib.util.module_from_spec(verify_spec)
with patch.dict(sys.modules, {"prepare": prepare}):
    verify_spec.loader.exec_module(verify)


class BuildLockTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "stacks/open5gs/sources.lock.json").read_text())

    def validate(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            path.write_text(json.dumps(value))
            return prepare.load_lock(path)

    def test_arm64_lock_has_main_and_transitive_sources(self):
        self.assertEqual(len(self.validate(self.lock)["sources"]), 3)

    def test_floating_source_and_mutable_image_are_rejected(self):
        for mutate in (lambda v: v["sources"][0].update(commit="main"),
                       lambda v: v["images"]["mongodb"].update(reference="mongo:8.0"),
                       lambda v: v["sources"][1].update(repository="unknown/freeDiameter")):
            value = copy.deepcopy(self.lock)
            mutate(value)
            with self.assertRaises(ValueError):
                self.validate(value)

    def test_duplicate_or_missing_transitive_source_rejected(self):
        self.lock["sources"][1] = self.lock["sources"][0]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.validate(self.lock)

    def test_archive_corruption_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.tar.gz"
            path.write_bytes(b"reviewed")
            source = {"name": "open5gs", "sha256": hashlib.sha256(b"reviewed").hexdigest()}
            prepare.verify_archive(path, source)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                prepare.verify_archive(path, source)

    def test_existing_build_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare.prepare(directory, Path(directory) / "cache")

    def test_bundle_excludes_apple_metadata_and_preserves_wrap(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "source"
            context.mkdir()
            (context / "good.wrap").write_text("[wrap-git]\n")
            (context / "._good.wrap").write_bytes(b"apple metadata")
            archive = Path(directory) / "bundle.tar.gz"
            prepare.pack(context, archive)
            with tarfile.open(archive) as bundle:
                self.assertIn("./good.wrap", bundle.getnames())
                self.assertNotIn("./._good.wrap", bundle.getnames())

    def test_real_meson_suite_names_and_no_partial_success(self):
        tests = [{"name": "open5gs:unit / " + name, "result": "OK"} for name in ("core", "crypt", "unit")]
        self.assertEqual(len(verify.verify_unit_suites(tests)), 3)
        for invalid in (tests[:2], tests + [tests[0]],
                        tests[:2] + [{"name": "open5gs:unit / unit", "result": "FAIL"}]):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                verify.verify_unit_suites(invalid)


if __name__ == "__main__":
    unittest.main()
