"""Lifecycle orchestration checks without service, Docker or modem mutations."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JETSON = load('jetson_platformctl', 'deploy/jetson/platformctl.py')
SPARK = load('spark_platformctl', 'deploy/spark/operations/platformctl.py')


def state(name, active=False):
    core = name == SPARK.CORE
    return dict(Id=name, LoadState='loaded', ActiveState='active' if active else 'inactive',
                SubState=('exited' if core else 'running') if active else 'dead',
                MainPID='123' if active and not core else '0', ControlPID='0')


class Host:
    def __init__(self, module, active=False):
        self.module = module
        self.units = {name: state(name, active) for name in module.UNITS}
        self.containers = [dict(service=name, state='running' if active else 'exited', health='healthy')
                           for name in SPARK.SERVICES]
        self.actions = []
        self.listener = active
        self.device_socket = active
        self.ue = dict(quality='ok', connected=False, recovery_paused=True)
        self.health = dict(status='ok', web='ok', collector='ok', device='ok')
        self.fail = None
        self.residual = None

    def maintain(self, action):
        if action in ('status', 'ue-status'):
            return {'platform': self.module.PLATFORM} if action == 'status' else self.ue
        self.actions.append(action)
        if action == self.fail:
            raise RuntimeError('Injected maintenance failure')
        start = action.endswith('start')
        if action.startswith('core-'):
            names = [SPARK.CORE]
            for container in self.containers:
                container['state'] = 'running' if start else 'exited'
        elif action.startswith('radio-'):
            names = [SPARK.RADIO]
        else:
            names = self.module.UNITS if self.module is JETSON else SPARK.MONITOR
            self.listener = start
            self.device_socket = start
        for name in names:
            self.units[name] = state(name, start)
        if self.residual and not start:
            self.residual(action)
        return {'completed': True}

    def waiting(self, check, description):
        if not check():
            raise RuntimeError('Timed out waiting for ' + description)

    def patched(self):
        stack = ExitStack()
        for name, value in [('units', lambda: self.units), ('maintain', self.maintain),
                            ('health', lambda: self.health), ('listening', lambda: self.listener),
                            ('wait_for', self.waiting)]:
            stack.enter_context(patch.object(self.module, name, value))
        if self.module is SPARK:
            stack.enter_context(patch.object(SPARK, 'containers', lambda: self.containers))
        else:
            stack.enter_context(patch.object(JETSON.Path, 'exists', lambda _: self.device_socket))
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(redirect_stderr(io.StringIO()))
        return stack


class LifecycleTests(unittest.TestCase):
    def test_spark_cold_start_and_idempotent_start(self):
        host = Host(SPARK)
        with host.patched():
            ctl = SPARK.Controller()
            ctl.start()
            ctl.start()
        self.assertEqual(host.actions, ['core-start', 'radio-start', 'start'])

    def test_spark_stop_order_and_idempotent_stop(self):
        host = Host(SPARK, True)
        with host.patched():
            ctl = SPARK.Controller()
            ctl.stop()
            ctl.stop()
        self.assertEqual(host.actions, ['radio-stop', 'core-stop', 'stop'])

    def test_partial_start_does_not_restart_existing_components(self):
        host = Host(SPARK, True)
        host.units[SPARK.RADIO] = state(SPARK.RADIO)
        host.units[SPARK.MONITOR[0]] = state(SPARK.MONITOR[0])
        with host.patched():
            SPARK.Controller().start()
        self.assertEqual(host.actions, ['radio-start', 'start'])

    def test_running_unhealthy_core_is_not_restarted(self):
        host = Host(SPARK, True)
        host.containers[0]['health'] = 'unhealthy'
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'unhealthy'):
            SPARK.Controller().start()
        self.assertEqual(host.actions, [])

    def test_partially_running_containers_require_inspection(self):
        host = Host(SPARK)
        host.containers[0]['state'] = 'running'
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'partially'):
            SPARK.Controller().start()
        self.assertEqual(host.actions, [])

    def test_missing_or_duplicate_core_service_is_not_healthy(self):
        healthy = Host(SPARK, True).containers
        self.assertFalse(SPARK.core_healthy(healthy[:-1]))
        self.assertFalse(SPARK.core_healthy(healthy[:-1] + [healthy[0]]))

    def test_start_failure_preserves_completed_stages(self):
        for action, expected in [('core-start', ['core-start']),
                                 ('radio-start', ['core-start', 'radio-start']),
                                 ('start', ['core-start', 'radio-start', 'start'])]:
            with self.subTest(action=action):
                host = Host(SPARK)
                host.fail = action
                with host.patched(), self.assertRaises(RuntimeError):
                    SPARK.Controller().start()
                self.assertEqual(host.actions, expected)

    def test_shutdown_failure_preserves_downstream_and_monitor(self):
        for action, expected in [('radio-stop', ['radio-stop']),
                                 ('core-stop', ['radio-stop', 'core-stop'])]:
            with self.subTest(action=action):
                host = Host(SPARK, True)
                host.fail = action
                with host.patched(), self.assertRaises(RuntimeError):
                    SPARK.Controller().stop()
                self.assertEqual(host.actions, expected)
                self.assertTrue(SPARK.running(host.units[SPARK.MONITOR[-1]]))

    def test_residual_gnb_process_prevents_core_stop(self):
        host = Host(SPARK, True)
        host.residual = lambda _: host.units[SPARK.RADIO].update(MainPID='456')
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'gNB shutdown'):
            SPARK.Controller().stop()
        self.assertEqual(host.actions, ['radio-stop'])

    def test_residual_core_containers_prevent_monitor_stop(self):
        host = Host(SPARK, True)
        def residual(action):
            if action == 'core-stop':
                host.containers[0]['state'] = 'running'
        host.residual = residual
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'Open5GS shutdown'):
            SPARK.Controller().stop()
        self.assertEqual(host.actions, ['radio-stop', 'core-stop'])

    def test_stopped_core_unit_with_running_containers_is_not_success(self):
        host = Host(SPARK)
        host.containers[0]['state'] = 'running'
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'Open5GS shutdown'):
            SPARK.Controller().stop()
        self.assertEqual(host.actions, [])

    def test_monitor_health_failure_does_not_restart_existing_stack(self):
        host = Host(SPARK, True)
        host.health['collector'] = 'stale'
        with host.patched(), self.assertRaisesRegex(RuntimeError, 'monitoring health'):
            SPARK.Controller().start()
        self.assertEqual(host.actions, [])

    def test_jetson_disconnected_start_reports_warning_without_recovery(self):
        host = Host(JETSON)
        host.health['device'] = 'unavailable'
        host.ue['quality'] = 'unavailable'
        with host.patched(), redirect_stdout(io.StringIO()) as output:
            ctl = JETSON.Controller()
            ctl.start()
            ctl.report()
            ctl.start()
        self.assertEqual(host.actions, ['start'])
        self.assertIn('no recovery was requested', output.getvalue())
        self.assertTrue(host.ue['recovery_paused'])

    def test_jetson_stop_and_repeat(self):
        host = Host(JETSON, True)
        with host.patched():
            ctl = JETSON.Controller()
            ctl.stop()
            ctl.stop()
        self.assertEqual(host.actions, ['stop'])

    def test_jetson_socket_or_listener_residue_is_failure(self):
        for residue in ('device_socket', 'listener'):
            with self.subTest(residue=residue):
                host = Host(JETSON, True)
                host.residual = lambda _: setattr(host, residue, True)
                with host.patched(), self.assertRaisesRegex(RuntimeError, 'Jetson shutdown'):
                    JETSON.Controller().stop()

    def test_private_socket_is_observable_without_directory_permission(self):
        with patch.object(JETSON.Path, 'exists', side_effect=PermissionError), \
                patch.object(JETSON, 'run', return_value='u_str LISTEN 0 0 /run/aoc-v2-jetson/device.sock 1 * 0'):
            self.assertEqual(JETSON.device_socket_state(), 'present (kernel)')

    def test_inaccessible_socket_is_never_inferred_absent(self):
        with patch.object(JETSON.Path, 'exists', side_effect=PermissionError), \
                patch.object(JETSON, 'run', return_value=''):
            self.assertEqual(JETSON.device_socket_state(), 'inaccessible')

    def test_inflight_service_operation_rejected(self):
        for module in (JETSON, SPARK):
            host = Host(module)
            host.units[module.UNITS[0]]['ActiveState'] = 'activating'
            with host.patched(), self.assertRaisesRegex(RuntimeError, 'in progress'):
                module.Controller().start()
            self.assertEqual(host.actions, [])

    def test_live_control_pid_is_not_quiescent(self):
        for module in (JETSON, SPARK):
            value = state(module.UNITS[0])
            value['ControlPID'] = '456'
            self.assertFalse(module.stopped(value))

    def test_fixed_helper_actions_and_noninteractive_timeout(self):
        for module in (JETSON, SPARK):
            with patch.object(module, 'run', return_value='{"completed":true}') as command:
                module.maintain('start')
                command.assert_called_once_with(['sudo', '-n', '/usr/local/sbin/aoc-maintain', 'start'], 330)
            for action in ('ue-recover', 'ue-resume', 'takeover', 'restart', 'shell'):
                with self.assertRaises(ValueError):
                    module.maintain(action)

    def test_permission_failure_is_nonzero_and_not_retried(self):
        for module in (JETSON, SPARK):
            host = Host(module)
            with host.patched(), tempfile.TemporaryDirectory() as directory, \
                    patch.object(module.Path, 'home', return_value=Path(directory)), \
                    patch.object(module.Controller, 'preflight', side_effect=RuntimeError('sudo denied')):
                self.assertEqual(module.main(['start']), 1)
            self.assertEqual(host.actions, [])

    def test_subprocess_timeout_is_nonzero_without_rollback(self):
        host = Host(SPARK)
        with host.patched(), tempfile.TemporaryDirectory() as directory, \
                patch.object(SPARK.Path, 'home', return_value=Path(directory)), \
                patch.object(SPARK.Controller, 'preflight'), \
                patch.object(SPARK, 'maintain', side_effect=subprocess.TimeoutExpired('helper', 330)) as action:
            self.assertEqual(SPARK.main(['start']), 1)
            action.assert_called_once_with('core-start')

    def test_operation_lock_conflict_and_release(self):
        for module in (JETSON, SPARK):
            with tempfile.TemporaryDirectory() as directory, patch.object(module.Path, 'home', return_value=Path(directory)):
                with module.operation_lock(), redirect_stderr(io.StringIO()):
                    self.assertEqual(module.main(['stop']), 3)
                with module.operation_lock():
                    pass

    def test_status_stopped_is_success_without_mutations(self):
        for module in (JETSON, SPARK):
            host = Host(module)
            with host.patched(), tempfile.TemporaryDirectory() as directory, \
                    patch.object(module.Path, 'home', return_value=Path(directory)), \
                    patch.object(module.Controller, 'preflight'):
                self.assertEqual(module.main(['status']), 0)
            self.assertEqual(host.actions, [])

    def test_wait_timeout_is_bounded(self):
        for module in (JETSON, SPARK):
            with patch.object(module.time, 'monotonic', side_effect=[0, 61]), \
                    self.assertRaisesRegex(RuntimeError, 'Timed out'):
                module.wait_for(lambda: False, 'test health')

    def test_docker_reads_only_owned_ids_without_private_inspection(self):
        template_output = 'aoc-v2-open5gs|amf|running|healthy\n'
        with patch.object(SPARK, 'run', side_effect=['owned-id\n', template_output]) as command:
            value = SPARK.containers()
        self.assertEqual(value[0]['service'], 'amf')
        commands = [call.args[0] for call in command.call_args_list]
        self.assertEqual(commands[0], ['docker', '--host', 'unix:///var/run/docker.sock', 'ps', '-aq', '--filter',
                                     'label=com.docker.compose.project=aoc-v2-open5gs'])
        self.assertEqual(commands[1][-1], 'owned-id')
        self.assertNotIn('.Config.Env', commands[1][5])

    def test_foreign_container_label_is_rejected(self):
        with patch.object(SPARK, 'run', side_effect=['id\n', 'other-project|amf|running|healthy\n']), \
                self.assertRaisesRegex(RuntimeError, 'ownership'):
            SPARK.containers()

    def test_systemctl_missing_unit_and_malformed_output_fail(self):
        for module in (JETSON, SPARK):
            with patch.object(module, 'run', return_value='Id=unknown.service\nLoadState=not-found\n'), \
                    self.assertRaisesRegex(RuntimeError, 'missing'):
                module.units()

    def test_health_does_not_use_environment_proxy(self):
        for module in (JETSON, SPARK):
            with patch.object(module.urllib.request, 'ProxyHandler') as proxy, \
                    patch.object(module.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"status":"ok"}'
                module.health()
            proxy.assert_called_once_with({})

    def test_wrapper_rejects_arguments_from_any_working_directory(self):
        for path in ('deploy/jetson', 'deploy/spark/operations'):
            for action in ('start', 'stop'):
                result = subprocess.run(['/bin/sh', str(ROOT / path / (action + '.sh')), 'unexpected'],
                                        cwd='/tmp', capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)

    def test_wrappers_locate_sibling_controller_from_another_directory(self):
        for area in ('deploy/jetson', 'deploy/spark/operations'):
            for action in ('start', 'stop'):
                with tempfile.TemporaryDirectory(prefix='aoc scripts ') as directory:
                    target = Path(directory)
                    wrapper = target / (action + '.sh')
                    wrapper.write_bytes((ROOT / area / wrapper.name).read_bytes())
                    (target / 'platformctl.py').write_text('import sys; print(sys.argv[1])\n')
                    result = subprocess.run(['/bin/sh', str(wrapper)], cwd='/tmp',
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), action)

    def test_health_deadline_caps_command_timeout_and_restores_budget(self):
        for module in (JETSON, SPARK):
            with patch.object(module, 'WAIT_DEADLINE', 60), \
                    patch.object(module.time, 'monotonic', return_value=55), \
                    patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')) as command:
                module.run(['systemctl', 'show'], timeout=20)
                self.assertEqual(command.call_args.kwargs['timeout'], 5)
            self.assertIsNone(module.WAIT_DEADLINE)


if __name__ == '__main__':
    unittest.main()
