import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core_render', ROOT / 'stacks/open5gs/compose/render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
runtime_spec = importlib.util.spec_from_file_location('core_runtime', ROOT / 'stacks/open5gs/compose/runtime.py')
runtime = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(runtime)


class BundleTests(unittest.TestCase):
    def test_mongo_mounts_readable_under_private_umask(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'bundle'
            previous = os.umask(0o077)
            try:
                render.render(out, project='aoc-v2-private-umask', database_auth=True)
            finally:
                os.umask(previous)
            compose = json.loads((out / 'compose.json').read_text())
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            self.assertEqual((out / 'secrets').stat().st_mode & 0o777, 0o700)
            mounts = compose['services']['mongo']['volumes']
            files = [out / mount.split(':')[0] for mount in mounts if mount.startswith('./')]
            self.assertEqual(len(files), 5)
            for path in files:
                with self.subTest(mount=path.name):
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_n6_is_opt_in_and_uses_separate_pinned_image(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'bundle'
            manifest = render.render(out, project='aoc-v2-test-n6', database_auth=True, n6=True)
            compose = json.loads((out / 'compose.json').read_text())
            self.assertEqual(compose['services']['upf']['image'], manifest['images']['n6'])
            self.assertFalse(compose['networks']['core']['internal'])
            self.assertNotIn('network_mode', compose['services']['upf'])
            self.assertNotIn('ports', compose['services']['upf'])
            self.assertEqual(compose['services']['upf']['environment'], {'AOC_N6_ENABLED': '1'})

    def test_nat_rules_only_own_table_and_ue_source_pool(self):
        self.assertIn('ip saddr 10.0.0.0/24', runtime.N6_RULES)
        self.assertIn('oifname "eth0"', runtime.N6_RULES)
        self.assertNotIn('flush', runtime.N6_RULES)
        self.assertIn('add table ip aoc_v2', runtime.N6_RULES)

    def test_authenticated_bundle_uses_secret_files_and_separate_db_user(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'bundle'
            manifest = render.render(out, project='aoc-v2-auth-test', database_auth=True)
            compose = json.loads((out / 'compose.json').read_text())
            mongo = compose['services']['mongo']
            self.assertTrue(manifest['database_auth'])
            self.assertIn('--auth', mongo['command'])
            self.assertTrue(all(key.endswith('_FILE') or key == 'MONGO_INITDB_DATABASE' for key in mongo['environment']))
            password = json.loads((out / 'secrets/subscriber-db.json').read_text())['password']
            self.assertNotIn(password, (out / 'compose.json').read_text())
            self.assertNotIn(password, (out / 'bundle.json').read_text())
            self.assertIn(password, (out / 'config/udr.json').read_text())
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)

    def test_connectivity_endpoint_serves_only_small_health_response(self):
        import http.client
        import threading
        with runtime.HTTPServer(('127.0.0.1', 0), runtime.ConnectivityHandler) as server:
            worker = threading.Thread(target=server.handle_request)
            worker.start()
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            connection.request('GET', '/health')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b'aoc-data-network-ok\n')
            connection.close()
            worker.join(3)

    def bundle(self, base):
        out = Path(base) / 'bundle'
        render.render(out, project='aoc-v2-test')
        return out, json.loads((out / 'compose.json').read_text())

    def test_each_nf_receives_own_config_and_immutable_image(self):
        with tempfile.TemporaryDirectory() as temp:
            out, compose = self.bundle(temp)
            self.assertEqual(set(compose['services']), set(render.ADDRESSES))
            for name, service in compose['services'].items():
                self.assertTrue(service['image'].startswith('sha256:'))
                self.assertEqual(service['pull_policy'], 'never')
                self.assertNotIn('ports', service)
                self.assertNotIn('privileged', service)
                if name not in ('mongo', 'ext-dn'):
                    self.assertIn(name, json.loads((out / 'config' / (name + '.json')).read_text()))
                    self.assertIn('./config/' + name + '.json:/etc/aoc/nf.json:ro', service['volumes'])

    def test_isolated_test_network_and_persistent_owned_database(self):
        with tempfile.TemporaryDirectory() as temp:
            _, compose = self.bundle(temp)
            self.assertTrue(compose['networks']['core']['internal'])
            self.assertEqual(compose['volumes']['mongo-data']['name'], 'aoc-v2-test-mongo')
            self.assertEqual(compose['services']['upf']['cap_add'], ['NET_ADMIN'])
            self.assertEqual(compose['services']['mongo']['user'], 'mongodb')
            for name in ('amf', 'udm', 'udr', 'ausf', 'pcf', 'nssf', 'smf'):
                self.assertIn('nrf', compose['services'][name]['depends_on'])

    def test_one_data_pool_direct_nrf_no_test_hnet_keys(self):
        addresses, configs = render.configurations('172.28.81.0/24')
        self.assertEqual(configs['smf']['smf']['session'], configs['upf']['upf']['session'])
        self.assertEqual(configs['smf']['smf']['pfcp']['client']['upf'][0]['address'], addresses['upf'])
        self.assertNotIn('hnet', configs['udm']['udm'])
        self.assertNotIn('freeDiameter', configs['smf']['smf'])
        self.assertEqual(configs['amf']['amf']['plmn_support'][0]['s_nssai'], [{'sst': 1}])

    def test_reject_overwrite_foreign_project_and_pool_overlap(self):
        with tempfile.TemporaryDirectory() as temp:
            out, _ = self.bundle(temp)
            with self.assertRaises(FileExistsError):
                render.render(out)
            with self.assertRaises(ValueError):
                render.render(Path(temp) / 'bad', project='foreign')
        with self.assertRaises(ValueError):
            render.configurations('10.0.0.0/24')


if __name__ == '__main__':
    unittest.main()
