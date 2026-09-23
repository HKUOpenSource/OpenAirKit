import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'stacks/open5gs/compose' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


render = module('connectivity_render', 'render.py')
upgrade = module('connectivity_upgrade', 'upgrade_connectivity.py')


class ConnectivityUpgradeTests(unittest.TestCase):
    def parent(self, bundle):
        (bundle.parent / 'runtime.py').write_text('unchanged radio runtime')
        release = {'files': {'core/' + name: hashlib.sha256((bundle / name).read_bytes()).hexdigest()
                             for name in upgrade.FILES}, 'release': 'fixture'}
        release['files']['runtime.py'] = hashlib.sha256((bundle.parent / 'runtime.py').read_bytes()).hexdigest()
        (bundle.parent / 'release.json').write_text(json.dumps(release))
        return release

    def test_upgrade_keeps_radio_parent_integrity_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'core'
            manifest = render.render(bundle, project='aoc-v2-open5gs')
            (bundle / 'runtime.py').write_text('previous runtime')
            manifest['files']['runtime.py'] = hashlib.sha256((bundle / 'runtime.py').read_bytes()).hexdigest()
            (bundle / 'bundle.json').write_text(json.dumps(manifest))
            before = self.parent(bundle)
            metadata = json.dumps([{'Id': manifest['images']['connectivity'], 'Architecture': 'arm64'}])
            with patch.object(upgrade, 'run', return_value=metadata), patch.object(upgrade, 'recreate'):
                upgrade.upgrade(bundle)
            after = upgrade.parent_release(bundle.resolve())
            self.assertEqual(after['files']['runtime.py'], before['files']['runtime.py'])
            self.assertEqual(after['release'], before['release'])
            self.assertNotEqual(after['files']['core/bundle.json'], before['files']['core/bundle.json'])

    def test_unrelated_parent_change_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'core'
            render.render(bundle, project='aoc-v2-open5gs')
            self.parent(bundle)
            (bundle.parent / 'runtime.py').write_text('unreviewed change')
            with patch.object(upgrade, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Parent release integrity failed'):
                    upgrade.upgrade(bundle)
                run.assert_not_called()
            self.assertFalse(list(bundle.parent.glob('connectivity-backup-*')))

    def test_failed_recreate_restores_exact_bundle_and_retries_old_container(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'core'
            manifest = render.render(bundle, project='aoc-v2-open5gs')
            self.parent(bundle)
            parent_before = (bundle.parent / 'release.json').read_bytes()
            before = {name: (bundle / name).read_bytes() for name in upgrade.FILES}
            metadata = json.dumps([{'Id': manifest['images']['connectivity'], 'Architecture': 'arm64'}])
            with patch.object(upgrade, 'run', return_value=metadata), \
                    patch.object(upgrade, 'recreate', side_effect=[RuntimeError('unhealthy'), None]) as recreate:
                with self.assertRaisesRegex(RuntimeError, 'unhealthy'):
                    upgrade.upgrade(bundle)
            self.assertEqual(recreate.call_count, 2)
            self.assertEqual(before, {name: (bundle / name).read_bytes() for name in upgrade.FILES})
            self.assertEqual(parent_before, (bundle.parent / 'release.json').read_bytes())
            upgrade.parent_release(bundle.resolve())
            self.assertEqual(len(list(bundle.parent.glob('connectivity-backup-*'))), 1)

    def test_upgrade_preserves_all_other_service_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'core'
            manifest = render.render(bundle, project='aoc-v2-open5gs')
            before = json.loads((bundle / 'compose.json').read_text())
            metadata = json.dumps([{'Id': manifest['images']['connectivity'], 'Architecture': 'arm64'}])
            with patch.object(upgrade, 'run', return_value=metadata), patch.object(upgrade, 'recreate'):
                result = upgrade.upgrade(bundle)
            after = json.loads((bundle / 'compose.json').read_text())
            self.assertTrue(result['upgraded'])
            for name in before['services']:
                if name != 'ext-dn':
                    self.assertEqual(before['services'][name], after['services'][name])
            upgrade.verify(bundle.resolve())

    def test_changed_bundle_rejected_before_docker_or_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'core'
            render.render(bundle, project='aoc-v2-open5gs')
            (bundle / 'runtime.py').write_text('changed')
            with patch.object(upgrade, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Bundle changed'):
                    upgrade.upgrade(bundle)
                run.assert_not_called()
            self.assertFalse(list(bundle.parent.glob('connectivity-backup-*')))
