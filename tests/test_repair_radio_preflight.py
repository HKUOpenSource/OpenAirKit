from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import repair_radio_preflight as repair


class RepairTests(unittest.TestCase):
    def environment(self, folder):
        root = Path(folder).resolve()
        install = root / 'install'
        old = install / 'releases' / 'original'
        old.mkdir(parents=True)
        units = root / 'units'
        units.mkdir()
        old_hashes = {}
        for name in repair.BASE:
            path = old / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('original ' + name)
            old_hashes[name] = repair.sha(path)
        bodies = {}
        for name in repair.UNITS:
            body = '[Unit]\nDescription=Test\n[Service]\nExecStart=' + str(old / 'bin/gnb') + '\n'
            (units / name).write_text(body)
            bodies[name] = body
        (old / 'release.json').write_text(json.dumps({'release_id': old.name, 'files': old_hashes,
            'units': {name: hashlib.sha256(body.encode()).hexdigest() for name, body in bodies.items()}}))
        (install / 'current').symlink_to(old)
        package = root / 'package'
        with patch('builtins.print'):
            repair.stage(package)
        runtime = Mock()
        runtime.switch_lock.side_effect = lambda: nullcontext()
        runtime.show.return_value = {'ActiveState': 'inactive', 'MainPID': '0'}
        return install, old, units, old_hashes, package, runtime, bodies

    def test_install_manifest_idempotence_and_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            install, old, units, hashes, package, runtime, bodies = self.environment(folder)
            with patch.object(repair, 'INSTALL', install), patch.object(repair, 'UNIT_DIR', units), \
                 patch.object(repair, 'BASE', hashes), patch.object(repair, 'call'), patch('builtins.print'):
                repair.install(runtime, package)
                current = (install / 'current').resolve()
                self.assertNotEqual(current, old)
                manifest = json.loads((current / 'release.json').read_text())
                for name, digest in manifest['files'].items():
                    self.assertEqual(repair.sha(current / name), digest)
                for name, digest in manifest['units'].items():
                    self.assertEqual(repair.sha(units / name), digest)
                    self.assertIn(str(current), (units / name).read_text())
                for name in hashes:
                    self.assertEqual(repair.sha(old / name), hashes[name])
                repair.install(runtime, package)
                self.assertEqual((install / 'current').resolve(), current)
                repair.restore(json.loads((current / 'preflight-fix.json').read_text()))
                self.assertEqual((install / 'current').resolve(), old)
                for name, body in bodies.items():
                    self.assertEqual((units / name).read_text(), body)

    def test_reload_failure_restores_pointer_and_units(self):
        with tempfile.TemporaryDirectory() as folder:
            install, old, units, hashes, package, runtime, bodies = self.environment(folder)
            reloads = []
            def call(argv):
                if argv == ['systemctl', 'daemon-reload']:
                    reloads.append(argv)
                    if len(reloads) == 1:
                        raise RuntimeError('reload failed')
            with patch.object(repair, 'INSTALL', install), patch.object(repair, 'UNIT_DIR', units), \
                 patch.object(repair, 'BASE', hashes), patch.object(repair, 'call', side_effect=call):
                with self.assertRaisesRegex(RuntimeError, 'reload failed'):
                    repair.install(runtime, package)
                self.assertEqual((install / 'current').resolve(), old)
                for name, body in bodies.items():
                    self.assertEqual((units / name).read_text(), body)
                self.assertEqual(len(reloads), 2)

    def test_active_service_rejected_without_changing_release(self):
        with tempfile.TemporaryDirectory() as folder:
            install, old, units, hashes, package, runtime, _ = self.environment(folder)
            runtime.show.return_value = {'ActiveState': 'active', 'MainPID': '123'}
            with patch.object(repair, 'INSTALL', install), patch.object(repair, 'UNIT_DIR', units), \
                 patch.object(repair, 'BASE', hashes), patch.object(repair, 'call') as call:
                with self.assertRaisesRegex(ValueError, 'Stop the new stack'):
                    repair.install(runtime, package)
                call.assert_not_called()
                self.assertEqual(list((install / 'releases').iterdir()), [old])

    def test_tampered_payload_rejected_before_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            install, old, units, hashes, package, runtime, _ = self.environment(folder)
            (package / 'scripts/radio_runtime.py').write_text('tampered')
            with patch.object(repair, 'INSTALL', install):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    repair.install(runtime, package)
                runtime.verify_release.assert_not_called()
                self.assertEqual((install / 'current').resolve(), old)


if __name__ == '__main__':
    unittest.main()
