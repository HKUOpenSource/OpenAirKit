import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import release_tools as release


class OfflineReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.lock = self.root / "requirements.lock"
        self.lock.write_text('example==1.0\n')
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()

    def wheel(self, tag="py3-none-any", dependencies="", python=">=3.10"):
        path = self.wheels / f"example-1.0-{tag}.whl"
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr("example-1.0.dist-info/METADATA",
                            f"Metadata-Version: 2.1\nName: example\nVersion: 1.0\nRequires-Python: {python}\n{dependencies}\n")
            bundle.writestr("example-1.0.dist-info/WHEEL", f"Wheel-Version: 1.0\nTag: {tag}\n")
            bundle.writestr("example-1.0.dist-info/RECORD", "")
        return path

    def test_target_markers_do_not_follow_build_interpreter(self):
        self.lock.write_text('example==1.0\nexceptiongroup==1.3.1; python_version < "3.11"\n')
        self.assertIn("exceptiongroup", release.locked_requirements(self.lock, "jetson"))
        self.assertNotIn("exceptiongroup", release.locked_requirements(self.lock, "spark"))

    def test_download_explicitly_selects_arm64_python_and_target_dependencies(self):
        self.lock.write_text('example==1.0; python_version < "3.11"\n')
        with patch.object(release.subprocess, "run") as run, patch.object(release, "validate_wheels"):
            release.download_wheels(self.wheels, self.lock, "jetson")
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("--python-version") + 1], "3.10")
        self.assertIn("manylinux_2_35_aarch64", argv)
        self.assertIn("cp310", argv)
        self.assertIn("example==1.0", argv)

    def test_valid_target_wheel_produces_checksum(self):
        path = self.wheel("cp310-cp310-manylinux_2_17_aarch64")
        self.assertEqual(release.validate_wheels(self.wheels, self.lock, "jetson"),
                         {path.name: hashlib.sha256(path.read_bytes()).hexdigest()})

    def test_rejects_wrong_architecture_python_and_glibc(self):
        for tag in ("cp310-cp310-macosx_11_0_arm64", "cp312-cp312-manylinux_2_17_aarch64",
                    "cp310-cp310-manylinux_2_17_x86_64", "cp310-cp310-manylinux_2_39_aarch64"):
            with self.subTest(tag=tag):
                path = self.wheel(tag)
                with self.assertRaisesRegex(ValueError, "incompatible"):
                    release.validate_wheels(self.wheels, self.lock, "jetson")
                path.unlink()

    def test_rejects_incomplete_and_corrupt_wheelhouse(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            release.validate_wheels(self.wheels, self.lock, "spark")
        self.wheel().write_bytes(b"not a wheel")
        with self.assertRaises(zipfile.BadZipFile):
            release.validate_wheels(self.wheels, self.lock, "spark")

    def test_renaming_a_wheel_cannot_hide_incompatible_internal_tags(self):
        self.wheel('cp310-cp310-manylinux_2_17_x86_64').rename(
            self.wheels / 'example-1.0-cp310-cp310-manylinux_2_17_aarch64.whl')
        with self.assertRaisesRegex(ValueError, "tags differ"):
            release.validate_wheels(self.wheels, self.lock, "jetson")

    def test_rejects_unlocked_transitive_dependency_and_python_requirement(self):
        path = self.wheel(dependencies="Requires-Dist: missing>=1\n")
        with self.assertRaisesRegex(ValueError, "does not satisfy"):
            release.validate_wheels(self.wheels, self.lock, "spark")
        path.unlink()
        self.wheel(python=">=3.12")
        with self.assertRaisesRegex(ValueError, "different Python"):
            release.validate_wheels(self.wheels, self.lock, "jetson")

    def test_archive_is_extractable_has_checksum_and_refuses_overwrite_or_symlink(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "RELEASE-VERSION").write_text("0.1.0\n")
        (stage / "manifest.json").write_text('{}\n')
        target = release.archive(stage, self.root, "spark")
        with tarfile.open(target) as bundle:
            self.assertIn("agentic-ocudu-spark-0.1.0-linux-arm64/manifest.json", bundle.getnames())
        self.assertEqual(target.with_suffix('.gz.sha256').read_text().split()[0], hashlib.sha256(target.read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            release.archive(stage, self.root, "spark")
        (stage / "unexpected").symlink_to(self.lock)
        with self.assertRaisesRegex(ValueError, "symlink"):
            release.archive(stage, self.root, "jetson")
