#!/usr/bin/python3 -I
"""Fixed project operations over root-owned, hash-approved release files."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

CONFIG = Path('/etc/aoc-maintenance.json')
BASE = Path('/opt/agentic-ocudu/maintenance')
STATE = Path('/var/lib/aoc-maintenance')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
ACTIONS = {
    'jetson': ('status', 'verify', 'install', 'rollback', 'start', 'stop',
               'ue-status', 'ue-maintenance', 'ue-resume', 'ue-recover', 'ue-job'),
    'spark': ('status', 'verify', 'install', 'rollback', 'start', 'stop',
              'radio-start', 'radio-stop', 'radio-restart', 'core-start', 'core-stop',
              'core-restart', 'connectivity-upgrade'),
}
UNITS = {
    'jetson': ('aoc-v2-jetson-web.service', 'aoc-v2-jetson-device.service'),
    'spark': ('aoc-control.service', 'aoc-observe.service', 'aoc-monitor-web.service'),
}


def secure(path):
    """Reject symlinks and any non-root writable ancestor, including the file."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Absolute protected path required')
    for entry in (path, *path.parents):
        info = entry.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Unprotected root operation path: ' + str(entry))
    return path


def approved(config):
    root = Path(config['approved'])
    if root.parent != BASE / 'approved' or not re.fullmatch('[a-f0-9]{64}', root.name):
        raise ValueError('Invalid approved bundle location')
    manifest_path = secure(root / 'manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != config['manifest_sha256']:
        raise ValueError('Approval manifest changed')
    if manifest['platform'] != config['platform']:
        raise ValueError('Approval platform mismatch')
    for name, digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Invalid manifest path')
        path = secure(root / name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Approved payload changed: ' + name)
    # No new Python modules or other files may be inserted into the approved tree.
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if not p.is_dir()}
    if actual != set(manifest['files']) | {'manifest.json'}:
        raise ValueError('Unapproved payload files')
    return root


def command(argv, timeout=300):
    # stdin is never inherited: an operation cannot collect passwords or code.
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, env=ENV, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Operation failed: ' + ' '.join(argv[:3]) + '\n' + result.stderr[-1200:])
    return result.stdout


def save(name, value):
    destination = STATE / name
    temporary = destination.with_name('.' + name + '.' + str(time.time_ns()))
    with temporary.open('x') as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output)
    temporary.replace(destination)


def rpc(request):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(8)
        connection.connect('/run/aoc-v2-jetson/device.sock')
        connection.sendall(json.dumps(request).encode() + b'\n')
        with connection.makefile('rb') as reader:
            raw = reader.readline(1024 * 1024)
        response = json.loads(raw)
    if not response.get('ok'):
        raise ValueError(response.get('error', 'Executor rejected request'))
    return response['result']


def ue(action):
    if action == 'ue-status':
        value = rpc({'op': 'status'})
        return {key: value.get(key) for key in ('quality', 'health', 'connected', 'registered',
                'data_session_active', 'lab_policy_match', 'management_protected', 'maintenance',
                'recovery_paused', 'connection_reason', 'evidence_at')}
    if action in ('ue-maintenance', 'ue-resume'):
        return rpc({'op': 'maintenance', 'enabled': action == 'ue-maintenance'})
    if action == 'ue-recover':
        config = rpc({'op': 'config'})
        job = rpc({'op': 'create', 'kind': 'recover', 'revision': config['revision']})
        save('ue-job.json', {'id': job['id']})
        rpc({'op': 'run', 'id': job['id'], 'confirmed': True})
        return {'id': job['id'], 'started': True}
    record = json.loads(secure(STATE / 'ue-job.json').read_text())
    job = rpc({'op': 'job', 'id': record['id']})
    return {key: job.get(key) for key in ('id', 'kind', 'state', 'phase', 'progress', 'error')}


def execute(config, action, root):
    platform = config['platform']
    stage = root / 'release'
    manager = stage / ('deploy/manage.py' if platform == 'jetson' else 'install.py')
    python = ['/usr/bin/python3', '-I', '-B', str(manager)]
    if action == 'status':
        units = UNITS[platform] + (('aoc-v2-core.service', 'aoc-v2-radio.service') if platform == 'spark' else ())
        return {'platform': platform, 'units': command(['/usr/bin/systemctl', 'show', *units,
                '-p', 'Id', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID'], 20)}
    if action == 'verify':
        command([*python, 'verify', '--stage' if platform == 'jetson' else '--path', str(stage)])
        return {'verified': True, 'approval': root.name}
    if action == 'install':
        # This helper upgrades existing commissioned installations only.
        auth = Path('/etc/aoc-v2-jetson/web.json' if platform == 'jetson' else '/etc/aoc-monitor/auth.json')
        secure(auth)
        if platform == 'jetson':
            before = set(Path('/opt/agentic-ocudu/jetson/backups').glob('*'))
            command([*python, 'stop'])
            try:
                command([*python, 'install', '--stage', str(stage)])
            finally:
                added = set(Path('/opt/agentic-ocudu/jetson/backups').glob('*')) - before
                if len(added) == 1:
                    backup = added.pop().name
                    if re.fullmatch('[0-9]+', backup):
                        save('jetson-rollback.json', {'backup': backup})
        else:
            command([*python, 'install', '--path', str(stage)])
        return {'installed': True, 'approval': root.name}
    if action == 'rollback':
        if platform == 'jetson':
            record = json.loads(secure(STATE / 'jetson-rollback.json').read_text())
            if not re.fullmatch('[0-9]+', record['backup']):
                raise ValueError('Invalid owned rollback checkpoint')
            command([*python, 'rollback', '--backup', record['backup']])
        else:
            command([*python, 'rollback'])
        return {'rolled_back': True}
    if action in ('start', 'stop'):
        if platform == 'jetson':
            command([*python, action])
        elif action == 'stop':
            command([*python, 'stop-platform'])
        else:
            command(['/usr/bin/systemctl', 'start', *UNITS[platform]])
        return {'action': action, 'completed': True}
    if action.startswith('ue-'):
        return ue(action)
    if action.startswith(('core-', 'radio-')):
        service, verb = action.split('-')
        command(['/usr/bin/systemctl', verb, 'aoc-v2-' + service + '.service'])
        return {'action': action, 'completed': True}
    if action == 'connectivity-upgrade':
        script = root / 'open5gs/compose/upgrade_connectivity.py'
        command(['/usr/bin/python3', '-I', '-B', str(script), '--bundle', '/opt/agentic-ocudu/v2/core'])
        return {'connectivity_upgraded': True}
    raise ValueError('Unknown operation')


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise ValueError('Use sudo -n /usr/local/sbin/aoc-maintain ACTION')
    config = json.loads(secure(CONFIG).read_text())
    action = sys.argv[1]
    if action not in ACTIONS.get(config.get('platform'), ()):
        raise ValueError('Operation is not allowed on this device')
    secure(STATE)
    descriptor = os.open(STATE / 'operation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        secure(STATE / 'operation.lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root = approved(config)
        started = time.time()
        try:
            result = execute(config, action, root)
        except Exception as error:
            save('last-operation.json', {'action': action, 'at': started, 'ok': False,
                                       'error': type(error).__name__})
            raise
        save('last-operation.json', {'action': action, 'at': started, 'ok': True})
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)[:1500]}), file=sys.stderr)
        raise SystemExit(1)
