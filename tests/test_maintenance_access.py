import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
from contextlib import ExitStack
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy/maintenance' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


bootstrap = load('maintenance_bootstrap', 'bootstrap.py')
helper = load('maintenance_helper', 'aoc-maintain.py')


class MaintenanceTests(unittest.TestCase):
    def existing_access(self, root):
        paths = {'BASE': root / 'base', 'STATE': root / 'state', 'HELPER': root / 'bin/helper',
                 'CONFIG': root / 'etc/config', 'POLICY': root / 'etc/policy'}
        previous = 'a' * 64
        approved = paths['BASE'] / 'approved' / previous
        approved.mkdir(parents=True)
        code = b'old approved helper'
        (approved / 'aoc-maintain.py').write_bytes(code)
        manifest = {'platform': 'jetson', 'files': {'aoc-maintain.py': hashlib.sha256(code).hexdigest()}}
        (approved / 'manifest.json').write_text(json.dumps(manifest))
        paths['STATE'].mkdir()
        (paths['STATE'] / 'operation.lock').touch()
        for name in ('HELPER', 'CONFIG', 'POLICY'):
            paths[name].parent.mkdir(parents=True, exist_ok=True)
        paths['HELPER'].write_bytes(code)
        config = {'approved': str(approved), 'account': 'matt', 'platform': 'jetson',
                  'manifest_sha256': hashlib.sha256((approved / 'manifest.json').read_bytes()).hexdigest()}
        paths['CONFIG'].write_text(json.dumps(config))
        with patch.multiple(bootstrap, **paths):
            paths['POLICY'].write_text(bootstrap.sudoers('matt', 'jetson'))
        return paths, previous

    def test_explicit_approval_replacement_preserves_policy_and_rolls_back_failed_activation(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temporary, ExitStack() as context:
                root = Path(temporary)
                paths, previous = self.existing_access(root)
                before = {key: paths[key].read_bytes() for key in ('HELPER', 'CONFIG', 'POLICY')}
                archive, digest = self.archive(root)
                context.enter_context(patch.multiple(bootstrap, **paths))
                context.enter_context(patch.object(bootstrap.os, 'geteuid', return_value=0))
                context.enter_context(patch.object(bootstrap.os, 'chown'))
                context.enter_context(patch.object(bootstrap, 'protected_file', side_effect=lambda p: p))
                context.enter_context(patch.object(bootstrap, 'protected_directory', side_effect=lambda p, *args: p.mkdir(parents=True, exist_ok=True)))
                context.enter_context(patch.object(bootstrap.platform, 'system', return_value='Linux'))
                context.enter_context(patch.object(bootstrap.platform, 'machine', return_value='aarch64'))
                context.enter_context(patch.object(bootstrap.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)))
                context.enter_context(patch.object(bootstrap, 'check_policy', side_effect=[None, RuntimeError('policy validation failed')] if fail else None))
                if fail:
                    with self.assertRaisesRegex(RuntimeError, 'policy validation failed'):
                        bootstrap.install(archive, digest, 'matt', replace_approval=previous)
                    self.assertEqual(before, {key: paths[key].read_bytes() for key in before})
                else:
                    result = bootstrap.install(archive, digest, 'matt', replace_approval=previous)
                    self.assertTrue(result['installed'])
                    self.assertEqual(paths['POLICY'].read_bytes(), before['POLICY'])
                    self.assertEqual(paths['HELPER'].read_bytes(), b'approved helper')
                    self.assertEqual(json.loads(paths['CONFIG'].read_text())['approved'], str(paths['BASE'] / 'approved' / digest))
                self.assertEqual(len(list(paths['BASE'].glob('access-backup-*'))), 1)

    def test_replacement_rejects_wrong_baseline_account_and_policy_expansion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, previous = self.existing_access(root)
            policy = root / 'next-policy'
            policy.write_bytes(paths['POLICY'].read_bytes())
            with patch.multiple(bootstrap, **paths), patch.object(bootstrap, 'protected_file', side_effect=lambda p: p):
                for baseline, account in (('b' * 64, 'matt'), (previous, 'other')):
                    with self.assertRaisesRegex(ValueError, 'differs'):
                        bootstrap.replacement_baseline(baseline, account, 'jetson', policy)
                policy.write_text('matt ALL=(root) NOPASSWD: ALL\n')
                with self.assertRaisesRegex(ValueError, 'exact existing sudo policy'):
                    bootstrap.replacement_baseline(previous, 'matt', 'jetson', policy)

    def archive(self, root, extra=None):
        files = {'aoc-maintain.py': b'approved helper', 'release/manifest.json': b'{}',
                 'release/deploy/manage.py': b'approved installer'}
        manifest = {'schema_version': 1, 'platform': 'jetson',
                    'files': {key: hashlib.sha256(value).hexdigest() for key, value in files.items()}}
        files['manifest.json'] = json.dumps(manifest).encode()
        target = root / 'approval.tar.gz'
        with tarfile.open(target, 'w:gz') as output:
            for name, value in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(value)
                output.addfile(info, io.BytesIO(value))
            if extra:
                output.addfile(extra)
        return target, hashlib.sha256(target.read_bytes()).hexdigest()

    def test_exact_commands_and_role_separation(self):
        self.assertEqual(bootstrap.ACTIONS, helper.ACTIONS)
        policy = bootstrap.sudoers('matt', 'jetson')
        self.assertIn('NOPASSWD: NOSETENV:', policy)
        self.assertNotIn('*', policy)
        self.assertNotIn('NOPASSWD: ALL', policy)
        self.assertNotIn('core-restart', policy)
        self.assertNotIn('/usr/bin/python', policy)
        self.assertNotIn('ue-recover', bootstrap.sudoers('defaultuser', 'spark'))
        with self.assertRaises(ValueError):
            bootstrap.sudoers('matt\nALL', 'jetson')

    def test_review_validates_payload_without_installing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, digest = self.archive(root)
            with patch.object(bootstrap.platform, 'system', return_value='Linux'), \
                    patch.object(bootstrap.platform, 'machine', return_value='aarch64'), \
                    patch.object(bootstrap.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)), \
                    patch.object(bootstrap, 'check_policy'), \
                    patch.object(bootstrap, 'protected_directory') as mutate:
                result = bootstrap.install(archive, digest, 'matt', check=True)
            self.assertFalse(result['installed'])
            mutate.assert_not_called()

    def test_archive_rejects_wrong_digest_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, digest = self.archive(root)
            output = root / 'payload'
            output.mkdir()
            with self.assertRaisesRegex(ValueError, 'checksum'):
                bootstrap.unpack(archive, '0' * 64, output)
            for name, kind in (('../escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)):
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = '/etc/sudoers'
                archive, digest = self.archive(root, item)
                with tempfile.TemporaryDirectory() as extraction:
                    with self.assertRaisesRegex(ValueError, 'regular files'):
                        bootstrap.unpack(archive, digest, Path(extraction))

    def test_approved_tree_rejects_modified_and_extra_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'approved' / ('a' * 64)
            root.mkdir(parents=True)
            (root / 'code.py').write_text('reviewed')
            manifest = {'platform': 'jetson', 'files': {'code.py': hashlib.sha256(b'reviewed').hexdigest()}}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            config = {'platform': 'jetson', 'approved': str(root),
                      'manifest_sha256': hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest()}
            with patch.object(helper, 'BASE', base), patch.object(helper, 'secure', side_effect=lambda p: Path(p)):
                self.assertEqual(helper.approved(config), root)
                (root / 'code.py').write_text('changed')
                with self.assertRaisesRegex(ValueError, 'payload changed'):
                    helper.approved(config)
                (root / 'code.py').write_text('reviewed')
                (root / 'extra.py').write_text('injected')
                with self.assertRaisesRegex(ValueError, 'Unapproved payload'):
                    helper.approved(config)

    def test_nonroot_writable_and_symlink_paths_rejected(self):
        for mode, uid in ((stat.S_IFREG | 0o644, 1000), (stat.S_IFREG | 0o664, 0),
                          (stat.S_IFLNK | 0o777, 0)):
            with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid)):
                with self.assertRaises(ValueError):
                    helper.secure(Path('/owned/code.py'))

    def test_additional_arguments_are_rejected_before_privileged_work(self):
        with patch.object(helper.os, 'geteuid', return_value=0), \
                patch.object(helper.sys, 'argv', ['aoc-maintain', 'install', '/tmp/other']), \
                patch.object(helper, 'secure') as secure:
            with self.assertRaises(ValueError):
                helper.main()
            secure.assert_not_called()

    def test_child_environment_and_input_are_fixed(self):
        completed = subprocess.CompletedProcess([], 0, 'ok', '')
        with patch.object(helper.subprocess, 'run', return_value=completed) as run:
            self.assertEqual(helper.command(['/usr/bin/systemctl', 'start', 'aoc-v2-core.service']), 'ok')
        self.assertEqual(run.call_args.kwargs['env'], helper.ENV)
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertNotIn('shell', run.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
