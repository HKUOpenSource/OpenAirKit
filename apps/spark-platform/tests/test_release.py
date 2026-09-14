import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from scripts.monitor_radio import load_renderer
from scripts.aoclib.radio import PROFILE
from scripts import monitor_release


class MonitorRadioReleaseTests(unittest.TestCase):
    def test_staged_renderer_import_and_opt_in_configuration(self):
        root=Path(__file__).resolve().parents[3]
        config=json.loads((root/'config/spark.example.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            package=Path(temporary)
            shutil.copyfile(root/'scripts/aoclib/radio.py',package/'radio-config.py')
            renderer=load_renderer(package)
            profile=dict(PROFILE,serial='PARSEONLY')
            plain=renderer.gnb_config(config,profile)
            self.assertFalse(plain['remote_control']['enabled'])
            enabled=renderer.gnb_config(config,dict(profile,telemetry_enabled=True))
            self.assertEqual(enabled['remote_control'],dict(enabled=True,bind_addr='127.0.0.1',port=8001))
            self.assertEqual(enabled['cell_cfg'],plain['cell_cfg'])
            self.assertEqual(enabled['ru_sdr'],plain['ru_sdr'])
            self.assertTrue(enabled['metrics']['enable_json'])


class V2MonitorReleaseTests(unittest.TestCase):
    def test_retired_unloaded_unit_is_already_stopped(self):
        missing = subprocess.CompletedProcess(
            ['systemctl', 'show', 'aoc-switch.service'], 0, stdout='not-found\n', stderr='')
        with patch.object(monitor_release.subprocess, 'run', return_value=missing) as run:
            self.assertFalse(monitor_release.stop_if_loaded('aoc-switch.service'))
        self.assertEqual(run.call_count, 1)

    def test_loaded_unit_stop_failure_is_not_hidden(self):
        loaded = subprocess.CompletedProcess(
            ['systemctl', 'show', 'aoc-monitor-web.service'], 0, stdout='loaded\n', stderr='')
        failed = subprocess.CalledProcessError(1, ['systemctl', 'stop', 'aoc-monitor-web.service'])
        with patch.object(monitor_release.subprocess, 'run', side_effect=[loaded, failed]):
            with self.assertRaises(subprocess.CalledProcessError):
                monitor_release.stop_if_loaded('aoc-monitor-web.service')

    def test_loopback_probe_reuses_time_wait_addresses(self):
        listener = unittest.mock.MagicMock()
        listener.__enter__.return_value = listener
        with patch.object(monitor_release.socket, 'socket', return_value=listener):
            self.assertTrue(monitor_release.loopback_port_available(8877))
        listener.setsockopt.assert_called_once_with(
            monitor_release.socket.SOL_SOCKET, monitor_release.socket.SO_REUSEADDR, 1)
        listener.bind.assert_called_once_with(('127.0.0.1', 8877))

    def test_loopback_wait_retries_then_succeeds(self):
        with patch.object(monitor_release, 'loopback_port_available', side_effect=[False, False, True]), \
             patch.object(monitor_release.time, 'sleep') as sleep:
            monitor_release.wait_for_loopback_port(8877, timeout=1)
        self.assertEqual(sleep.call_count, 2)

    def test_stage_is_locked_single_stack_and_has_restricted_control_executor(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / 'release'
            monitor_release.stage(stage)
            manifest = monitor_release.verify(stage)
            files = set(manifest['files'])
            self.assertEqual({p.name for p in (stage / 'deploy').iterdir()},
                             {'aoc-control.service', 'aoc-observe.service', 'aoc-monitor-web.service'})
            self.assertNotIn('backend/aoc_spark/executor.py', files)
            self.assertNotIn('deploy/aoc-switch.service', files)
            self.assertIn('backend/aoc_spark/control.py', files)
            self.assertIn('requirements.lock', files)
            self.assertIn('radio-metrics.py', files)
            requirements = (stage / 'requirements.lock').read_text().splitlines()
            self.assertTrue(requirements)
            self.assertTrue(all('==' in line for line in requirements if line and not line.startswith('#')))
            source = '\n'.join((stage / 'backend' / 'aoc_spark' / name).read_text()
                               for name in ('collector.py', 'connectivity.py', 'domain.py', 'telemetry.py', 'web.py'))
            for forbidden in ('aoc-cn5g', '172.28.80.', 'aoc-gnb.service', 'LegacyFeed', 'parse_smf'):
                self.assertNotIn(forbidden, source)
            control = (stage / 'backend/aoc_spark/control.py').read_text()
            self.assertIn('"start": (("start",),)', control)
            self.assertNotIn('shell=True', control)
            web_unit = (stage / 'deploy/aoc-monitor-web.service').read_text()
            self.assertIn('InaccessiblePaths=-/run/docker.sock -/var/run/docker.sock', web_unit)

    def test_installer_has_database_and_config_rollback_and_bounded_platform_stop(self):
        source = Path(monitor_release.__file__).read_text()
        self.assertIn('"database_backup"', source)
        self.assertIn('"web_config"', source)
        self.assertIn('def stop_platform():', source)
        self.assertIn('/run/aoc-control/control.sock', source)


if __name__=='__main__':
    unittest.main()
