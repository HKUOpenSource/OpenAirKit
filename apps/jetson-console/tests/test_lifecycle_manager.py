"""Independent commissioning and lifecycle, with no systemd or modem writes."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('lifecycle_manager', ROOT / 'deploy/jetson/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class ManagerTests(unittest.TestCase):
    def start_context(self, active=False, maintenance=True, job=None):
        context = ExitStack()
        context.enter_context(patch('aoc_jetson.config.load', return_value={
            'commissioned': True, 'management_verified': True}))
        context.enter_context(patch.object(manager, 'unit_state', return_value='active' if active else 'inactive'))
        context.enter_context(patch.object(manager.socket, 'socket'))
        context.enter_context(patch.object(manager, 'wait_device', return_value={
            'maintenance': maintenance, 'recovery_paused': True}))
        request = context.enter_context(patch.object(manager, 'device_request', return_value={'active_job': job}))
        network = context.enter_context(patch.object(manager, 'network_action', return_value={'ok': True}))
        command = context.enter_context(patch.object(manager, 'output', return_value=''))
        context.enter_context(redirect_stdout(io.StringIO()))
        return context, request, network, command

    def test_cold_start_prepares_routes_and_resumes_observation(self):
        context, request, network, command = self.start_context()
        with context:
            manager.start()
        network.assert_called_once_with('prepare')
        request.assert_called_once_with({'op': 'maintenance', 'enabled': False})
        self.assertTrue(any('site_guard.py' in ' '.join(c.args[0]) for c in command.call_args_list))
        self.assertFalse(any('restart' in c.args[0] for c in command.call_args_list))

    def test_repeated_start_does_not_clear_current_observation(self):
        context, request, network, command = self.start_context(active=True, maintenance=False)
        with context:
            manager.start()
        request.assert_called_once_with({'op': 'status'})
        network.assert_called_once_with('prepare')
        self.assertFalse(any('restart' in c.args[0] for c in command.call_args_list))

    def test_running_device_job_blocks_lifecycle_mutation(self):
        context, request, network, command = self.start_context(active=True, job={'state': 'running'})
        with context, self.assertRaisesRegex(ValueError, 'device operation is active'):
            manager.start()
        network.assert_not_called()
        command.assert_not_called()

    def test_route_conflict_prevents_service_start(self):
        context, request, network, command = self.start_context()
        network.side_effect = ValueError('Route conflict')
        with context, self.assertRaisesRegex(ValueError, 'Route conflict'):
            manager.start()
        self.assertFalse(any(c.args[0][:2] == ['systemctl', 'start'] for c in command.call_args_list))
        request.assert_not_called()

    def test_stop_cleans_journal_even_when_services_are_already_stopped(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / 'network-state.json').write_text('{"routes": []}')
            with patch.object(manager, 'STATE', state), \
                    patch.object(manager, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')), \
                    patch.object(manager, 'unit_state', return_value='inactive'), \
                    patch.object(manager, 'network_action', side_effect=ValueError('Changed owned route')) as network:
                with self.assertRaisesRegex(ValueError, 'Changed owned route'):
                    manager.stop()
                network.assert_called_once_with('restore')

    def test_commission_refuses_serial_owner_without_stopping_it(self):
        config = json.loads((ROOT / 'config/jetson.example.json').read_text())
        with patch('aoc_jetson.config.load', return_value=config), \
                patch('aoc_jetson.hardware.discover', return_value={'at_port': '/dev/test-at'}), \
                patch.object(manager, 'unit_state', return_value='inactive'), \
                patch.object(manager, 'run', return_value=SimpleNamespace(returncode=0)) as command, \
                patch.object(manager, 'private_write') as write:
            with self.assertRaisesRegex(ValueError, 'serial port is in use'):
                manager.commission('192.0.2.20', 'wifi0')
        command.assert_called_once_with(['fuser', '/dev/test-at'], timeout=5, check=False)
        write.assert_not_called()

    def test_system_python_commission_reexecs_installed_runtime(self):
        with patch.object(manager.os, 'geteuid', return_value=0), \
                patch.object(manager.sys, 'argv', ['manage.py', 'commission', '--spark-address', '192.0.2.20']), \
                patch.object(manager.os, 'execv', side_effect=RuntimeError('reexec')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'reexec'):
                manager.main()
        self.assertEqual(execute.call_args.args[0], '/opt/agentic-ocudu/jetson/current/venv/bin/python')
        self.assertEqual(execute.call_args.args[1][1:3], ['-I', '-B'])


if __name__ == '__main__':
    unittest.main()
