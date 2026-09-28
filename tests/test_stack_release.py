"""Offline stack packaging/installation contract; no Docker/systemd/RF execution."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from stacks.open5gs.compose.render import render

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stack_package', ROOT / 'deploy/spark/stack/package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class StackReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.core = self.root / 'core'
        render(self.core, database_auth=True, n6=True)
        self.binary = self.root / 'gnb'
        self.probe = self.root / 'probe'
        header = b'\x7fELF\x02\x01' + bytes(12) + (183).to_bytes(2, 'little')
        self.binary.write_bytes(header + b'synthetic gnb')
        self.probe.write_bytes(header + b'synthetic probe')
        self.record = self.root / 'build-result.json'
        self.record.write_text(json.dumps(dict(commit=package.PINNED_OCUDU, architecture='aarch64',
                                              sha256=package.runtime.digest(self.binary))))
        self.output = self.root / 'release'

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self):
        return package.stage(self.core, self.binary, self.probe, self.record, self.output)

    def test_supported_entrypoints_help_needs_no_privilege_or_hardware(self):
        for path in ('scripts/aocctl', 'deploy/spark/stack/runtime.py', 'deploy/spark/stack/package.py'):
            result = subprocess.run([sys.executable, str(ROOT / path), '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_stage_verifies_offline_and_preserves_core_without_starting_services(self):
        before = package.files(self.core)
        with patch.object(package.runtime, 'run', side_effect=AssertionError('No host commands during stage')):
            release = self.stage()
            self.assertEqual(package.verify(self.output), release)
        self.assertEqual(package.files(self.output / 'core'), before)
        self.assertFalse(release['rf_accepted'])
        self.assertEqual(release['source_commit'], json.loads((ROOT / 'config/upstreams.json').read_text())['ocudu']['commit'])
        self.assertFalse(any('/archive/' in n or 'jetson' in n for n in release['files']))
        for name in package.UNIT_NAMES:
            unit = (self.output / 'systemd' / name).read_text()
            self.assertNotIn('[Install]', unit)
            self.assertNotIn('aoc-monitor', unit)

    def test_stage_rejects_changed_build_and_unlisted_core_file(self):
        self.binary.write_bytes(self.binary.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'build record'):
            self.stage()
        self.assertFalse(self.output.exists())
        (self.core / 'unexpected.py').write_text('unreviewed')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            self.stage()

    def test_verify_rejects_changes_additions_and_symlink_parents(self):
        self.stage()
        path = self.output / 'runtime.py'
        original = path.read_bytes()
        path.write_bytes(original + b'\n# changed')
        with self.assertRaises(ValueError):
            package.verify(self.output)
        path.write_bytes(original)
        extra = self.output / 'unexpected.py'
        extra.write_text('extra')
        with self.assertRaises(ValueError):
            package.verify(self.output)
        extra.unlink()
        (self.output / 'bin').rename(self.root / 'outside')
        (self.output / 'bin').symlink_to(self.root / 'outside', target_is_directory=True)
        with self.assertRaises(ValueError):
            package.verify(self.output)

    def install_context(self, fail_reload=False):
        base = self.root / 'installed' / 'v2'
        unit_dir = self.root / 'units'; unit_dir.mkdir()
        cli = self.root / 'aoc-v2ctl'
        calls = []
        def run(argv, timeout=30):
            calls.append(argv)
            if argv[:2] == ['systemctl', 'show']:
                return 'not-found\n'
            if argv[:2] == ['systemd-analyze', 'verify']:
                self.assertFalse(base.exists())
                self.assertTrue(all(Path(name).is_file() for name in argv[2:]))
            if fail_reload and argv == ['systemctl', 'daemon-reload'] and calls.count(argv) == 1:
                raise RuntimeError('Synthetic reload failure')
            return ''
        stack = ExitStack()
        for obj, name, value in ((package.os, 'geteuid', lambda: 0),
                                  (package.os, 'chown', lambda *_: None),
                                  (package.platform, 'system', lambda: 'Linux'),
                                  (package.platform, 'machine', lambda: 'aarch64'),
                                  (package, 'UNIT_DIR', unit_dir), (package, 'CLI', cli),
                                  (package.runtime, 'BASE', base),
                                  (package.runtime, 'resources', lambda _: None),
                                  (package.runtime, 'containers', lambda: []),
                                  (package.runtime, 'run', run)):
            stack.enter_context(patch.object(obj, name, value))
        return stack, base, unit_dir, cli, calls

    def test_install_only_copies_units_and_reloads_and_refuses_reuse(self):
        self.stage()
        context, base, unit_dir, cli, calls = self.install_context()
        with context:
            package.install(self.output)
            self.assertEqual(cli.resolve(), (base / 'aocctl').resolve())
            self.assertEqual({p.name for p in unit_dir.iterdir()}, set(package.UNIT_NAMES))
            self.assertEqual((base / 'core/config/amf.json').stat().st_mode & 0o777, 0o644)
            self.assertEqual((base / 'core').stat().st_mode & 0o777, 0o700)
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                package.install(self.output)
        self.assertFalse(any(c[:2] in (['systemctl', 'start'], ['systemctl', 'enable']) for c in calls))

    def test_failed_install_removes_only_new_files(self):
        self.stage()
        context, base, unit_dir, cli, calls = self.install_context(fail_reload=True)
        with context, self.assertRaisesRegex(RuntimeError, 'Synthetic reload failure'):
            package.install(self.output)
        self.assertFalse(base.exists())
        self.assertFalse(cli.is_symlink())
        self.assertEqual(list(unit_dir.iterdir()), [])
        self.assertTrue(self.output.exists())
        self.assertEqual(calls.count(['systemctl', 'daemon-reload']), 2)


if __name__ == '__main__':
    unittest.main()
