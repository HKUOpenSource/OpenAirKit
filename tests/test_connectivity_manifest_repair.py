import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_connectivity_upgrade import render, upgrade

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('connectivity_manifest_repair',
    ROOT / 'deploy/maintenance/repair-connectivity-manifest.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class ManifestRepairTests(unittest.TestCase):
    def setUp(self):
        # Model the installed root ownership while preserving actual file types
        # and modes, including the old installer's group-writable directories.
        lstat = Path.lstat
        def root_owned(path):
            values = list(lstat(path))
            values[4] = values[5] = 0
            return os.stat_result(values)
        owned = patch.object(Path, 'lstat', root_owned)
        owned.start()
        self.addCleanup(owned.stop)

    def fixture(self, base):
        core = base / 'core'
        bundle = render.render(core, project='aoc-v2-open5gs')
        (base / 'runtime.py').write_text('unchanged installed radio runtime')
        (core / 'runtime.py').write_text('previous ext-DN runtime')
        bundle['files']['runtime.py'] = hashlib.sha256((core / 'runtime.py').read_bytes()).hexdigest()
        (core / 'bundle.json').write_text(json.dumps(bundle))
        files = {'core/' + name: hashlib.sha256((core / name).read_bytes()).hexdigest() for name in repair.FILES}
        files['runtime.py'] = hashlib.sha256((base / 'runtime.py').read_bytes()).hexdigest()
        before = json.dumps({'files': files, 'release': 'untouched identifier'}).encode()
        (base / 'release.json').write_bytes(before)
        image = json.dumps([{'Id': repair.IMAGE, 'Architecture': 'arm64'}])
        with patch.object(upgrade, 'run', return_value=image), patch.object(upgrade, 'recreate'):
            upgrade.upgrade(core)
        expected = json.loads((base / 'release.json').read_bytes())
        # Reproduce the earlier updater: core changed but parent hashes stayed old.
        (base / 'release.json').write_bytes(before)
        return before, expected

    def test_old_directory_modes_are_tightened_without_changing_binary(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(repair, 'secure', side_effect=lambda p: p):
            base = Path(temporary).resolve()
            self.fixture(base)
            binary = base / 'bin/gnb'
            binary.parent.mkdir(mode=0o775)
            binary.parent.chmod(0o775)
            binary.write_bytes(b'unchanged reviewed binary')
            binary.chmod(0o755)
            release = json.loads((base / 'release.json').read_text())
            release['files']['bin/gnb'] = hashlib.sha256(binary.read_bytes()).hexdigest()
            (base / 'release.json').write_text(json.dumps(release))
            result = repair.repair(base)
            self.assertEqual(binary.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual(binary.read_bytes(), b'unchanged reviewed binary')
            self.assertEqual(result['directory_permissions_tightened'], ['bin'])
            receipt = Path(result['backup'] + '.permissions.json')
            self.assertEqual(json.loads(receipt.read_text())['bin'], {'before': 0o775, 'after': 0o755})

    def test_failed_verification_restores_directory_modes(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(repair, 'secure', side_effect=lambda p: p):
            base = Path(temporary).resolve()
            before, _ = self.fixture(base)
            (base / 'core').chmod(0o775)
            (base / 'runtime.py').write_text('unreviewed change')
            with self.assertRaisesRegex(ValueError, 'Unrelated release change'):
                repair.repair(base)
            self.assertEqual((base / 'core').stat().st_mode & 0o777, 0o775)
            self.assertEqual((base / 'release.json').read_bytes(), before)

    def test_directory_repair_rejects_public_root_world_write_and_links(self):
        for kind in ('public-root', 'world-write', 'symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(repair, 'secure', side_effect=lambda p: p):
                base = Path(temporary).resolve()
                before, _ = self.fixture(base)
                if kind == 'public-root':
                    base.chmod(0o755)
                elif kind == 'world-write':
                    (base / 'core').chmod(0o777)
                else:
                    (base / 'core').rename(base / 'elsewhere')
                    (base / 'core').symlink_to(base / 'elsewhere')
                with self.assertRaises(ValueError):
                    repair.repair(base)
                self.assertEqual((base / 'release.json').read_bytes(), before)

    def test_repair_accepts_only_reviewed_delta_and_restores_parent_integrity(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(repair, 'secure', side_effect=lambda p: p):
            base = Path(temporary).resolve()
            before, expected = self.fixture(base)
            contents = {p: p.read_bytes() for p in (base / 'core').rglob('*') if p.is_file()}
            result = repair.repair(base)
            self.assertEqual(json.loads((base / 'release.json').read_bytes()), expected)
            self.assertEqual(Path(result['backup']).read_bytes(), before)
            self.assertEqual(contents, {p: p.read_bytes() for p in contents})
            self.assertFalse(result['services_changed'])
            upgrade.parent_release(base / 'core')

    def test_unrelated_radio_or_compose_changes_are_rejected_without_writes(self):
        for target in ('runtime.py', 'core/compose.json'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(repair, 'secure', side_effect=lambda p: p):
                base = Path(temporary).resolve()
                before, _ = self.fixture(base)
                path = base / target
                if target.endswith('.json'):
                    value = json.loads(path.read_text())
                    value['services']['ext-dn']['privileged'] = True
                    path.write_text(json.dumps(value))
                else:
                    path.write_text('changed radio runtime')
                with self.assertRaises(ValueError):
                    repair.repair(base)
                self.assertEqual((base / 'release.json').read_bytes(), before)
                self.assertFalse(list(base.glob('release.json.connectivity-before-*')))

    def test_missing_baseline_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(repair, 'secure', side_effect=lambda p: p):
            base = Path(temporary).resolve()
            before, _ = self.fixture(base)
            for backup in base.glob('connectivity-backup-*'):
                (backup / 'runtime.py').write_text('not the original')
            with self.assertRaisesRegex(ValueError, 'No intact backup'):
                repair.repair(base)
            self.assertEqual((base / 'release.json').read_bytes(), before)

    def test_post_write_failure_restores_original_parent_bytes(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(repair, 'secure', side_effect=lambda p: p):
            base = Path(temporary).resolve()
            before, _ = self.fixture(base)
            real_read = repair.read
            def changed_after_write(path):
                value = real_read(path)
                if path == base / 'release.json' and path.read_bytes() != before:
                    value['files']['runtime.py'] = '0' * 64
                return value
            with patch.object(repair, 'read', side_effect=changed_after_write):
                with self.assertRaisesRegex(ValueError, 'Post-repair integrity failed'):
                    repair.repair(base)
            self.assertEqual((base / 'release.json').read_bytes(), before)

    def test_reviewed_runtime_pin_matches_source(self):
        self.assertEqual(repair.RUNTIME_SHA, hashlib.sha256(
            (ROOT / 'stacks/open5gs/compose/runtime.py').read_bytes()).hexdigest())
