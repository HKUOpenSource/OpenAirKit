#!/usr/bin/env python3
"""Install a reviewed maintenance bundle; initial execution requires sudo."""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

BASE = Path('/opt/agentic-ocudu/maintenance')
HELPER = Path('/usr/local/sbin/aoc-maintain')
CONFIG = Path('/etc/aoc-maintenance.json')
POLICY = Path('/etc/sudoers.d/aoc-maintenance')
STATE = Path('/var/lib/aoc-maintenance')
# Keep policy generation independent from code loaded from an untrusted archive.
ACTIONS = {
    'jetson': ('status', 'verify', 'install', 'rollback', 'start', 'stop',
               'ue-status', 'ue-maintenance', 'ue-resume', 'ue-recover', 'ue-job'),
    'spark': ('status', 'verify', 'install', 'rollback', 'start', 'stop',
              'radio-start', 'radio-stop', 'radio-restart', 'core-start', 'core-stop',
              'core-restart', 'connectivity-upgrade'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(archive, digest, output):
    """Validate before installing or executing any bundle code."""
    if not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('Archive checksum mismatch')
    seen = set()
    size = 0
    # Hash a private snapshot, so the SSH account cannot change bytes between
    # verification and privileged extraction.
    with tempfile.TemporaryFile() as snapshot:
        checksum = hashlib.sha256()
        compressed_size = 0
        with archive.open('rb') as incoming:
            while chunk := incoming.read(1024 * 1024):
                compressed_size += len(chunk)
                if compressed_size > 1024 ** 3:
                    raise ValueError('Approval archive exceeds limits')
                checksum.update(chunk)
                snapshot.write(chunk)
        if checksum.hexdigest() != digest:
            raise ValueError('Archive checksum mismatch')
        snapshot.seek(0)
        with tarfile.open(fileobj=snapshot, mode='r:gz') as source:
            for item in source:
                name = Path(item.name)
                if not item.isfile() or name.is_absolute() or '..' in name.parts or item.name in seen:
                    raise ValueError('Only unique relative regular files are allowed')
                seen.add(item.name)
                size += item.size
                if size > 1024 ** 3 or len(seen) > 2000:
                    raise ValueError('Approval bundle exceeds limits')
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(item) as stream, destination.open('xb') as target:
                    shutil.copyfileobj(stream, target)
                destination.chmod(0o600)
    manifest = json.loads((output / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('platform') not in ACTIONS:
        raise ValueError('Unknown approval manifest')
    if seen != set(manifest['files']) | {'manifest.json'}:
        raise ValueError('Unapproved archive members')
    for name, expected in manifest['files'].items():
        if sha(output / name) != expected:
            raise ValueError('Payload checksum mismatch: ' + name)
    if not {'aoc-maintain.py', 'release/manifest.json'} <= seen:
        raise ValueError('Incomplete maintenance bundle')
    required = 'release/deploy/manage.py' if manifest['platform'] == 'jetson' else 'release/install.py'
    if required not in seen:
        raise ValueError('Missing approved installer')
    return manifest


def sudoers(user, kind):
    if not re.fullmatch('[a-z_][a-z0-9_-]{0,31}', user):
        raise ValueError('Invalid maintenance account')
    commands = ', '.join(str(HELPER) + ' ' + action for action in ACTIONS[kind])
    return '# Agentic-OCUDU reviewed maintenance only\n' + user + ' ALL=(root) NOPASSWD: NOSETENV: ' + commands + '\n'


def check_policy(path):
    tool = shutil.which('visudo', path='/usr/sbin:/usr/bin:/sbin:/bin')
    if not tool:
        raise ValueError('visudo is required')
    subprocess.run([tool, '-c', '-f', str(path)], check=True, timeout=15)


def protected_directory(path, mode=0o755):
    # Inspect existing ancestors before any mkdir/chmod or traversal through them.
    for parent in reversed((path, *path.parents)):
        if not parent.exists() and not parent.is_symlink():
            parent.mkdir(mode=mode if parent == path else 0o755)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Unsafe privileged directory: ' + str(parent))


def protected_file(path):
    for entry in (path, *path.parents):
        info = entry.lstat()
        expected = stat.S_ISREG if entry == path else stat.S_ISDIR
        if not expected(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Unsafe existing maintenance file: ' + str(entry))
    return path


def replacement_baseline(previous, user, kind, policy):
    config = json.loads(protected_file(CONFIG).read_bytes())
    root = BASE / 'approved' / previous
    if (config.get('approved') != str(root) or config.get('account') != user
            or config.get('platform') != kind):
        raise ValueError('Existing approval/account/role differs from the reviewed replacement')
    manifest_path = protected_file(root / 'manifest.json')
    if sha(manifest_path) != config.get('manifest_sha256'):
        raise ValueError('Existing approval manifest changed')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('platform') != kind:
        raise ValueError('Existing approval role changed')
    for name, expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe existing approval path')
        if sha(protected_file(root / name)) != expected:
            raise ValueError('Existing approved payload changed')
    if sha(protected_file(HELPER)) != manifest['files']['aoc-maintain.py']:
        raise ValueError('Existing installed helper changed')
    if protected_file(POLICY).read_bytes() != policy.read_bytes():
        raise ValueError('Replacement must preserve the exact existing sudo policy')
    return {path: (protected_file(path).read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in (HELPER, CONFIG, POLICY)}


def replace_file(path, contents, mode):
    fd, temporary = tempfile.mkstemp(prefix='.aoc-maintenance-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(archive, digest, user, check=False, replace_approval=None):
    if not check and os.geteuid() != 0:
        raise ValueError('Initial configuration requires sudo in your device terminal')
    if replace_approval is not None and not re.fullmatch('[a-f0-9]{64}', replace_approval):
        raise ValueError('Replacement requires the previous approval SHA-256')
    with ExitStack() as locks, tempfile.TemporaryDirectory(prefix='aoc-maintenance-review-') as temporary:
        payload = Path(temporary) / 'payload'
        payload.mkdir(mode=0o700)
        manifest = unpack(archive, digest, payload)
        kind = manifest['platform']
        account = pwd.getpwnam(user)
        if account.pw_uid == 0:
            raise ValueError('Use the ordinary SSH account')
        if platform.system() != 'Linux' or platform.machine() != 'aarch64':
            raise ValueError('Linux ARM64 device required')
        policy = Path(temporary) / 'sudoers'
        policy.write_text(sudoers(user, kind))
        policy.chmod(0o440)
        check_policy(policy)
        if check:
            return {'checked': True, 'platform': kind, 'account': user,
                    'sha256': digest, 'allowed_actions': ACTIONS[kind], 'installed': False}
        old = None
        if replace_approval:
            lock = locks.enter_context(protected_file(STATE / 'operation.lock').open('r+'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            old = replacement_baseline(replace_approval, user, kind, policy)
        elif any(path.exists() or path.is_symlink() for path in (HELPER, CONFIG, POLICY)):
            raise ValueError('Existing maintenance configuration requires explicit administrator review')
        protected_directory(BASE / 'approved')
        protected_directory(HELPER.parent)
        protected_directory(POLICY.parent)
        protected_directory(STATE, 0o700)
        destination = BASE / 'approved' / digest
        if destination.exists():
            raise ValueError('Approval destination already exists')
        shutil.copytree(payload, destination)
        for path in (destination, *destination.rglob('*')):
            os.chown(path, 0, 0)
            path.chmod(0o755 if path.is_dir() else 0o644)
        config = {'schema_version': 1, 'platform': kind, 'account': user,
                  'approved': str(destination), 'manifest_sha256': sha(destination / 'manifest.json')}
        if old:
            saved = BASE / ('access-backup-' + str(time.time_ns()))
            saved.mkdir(mode=0o700)
            for target, (contents, mode) in old.items():
                (saved / target.name).write_bytes(contents)
                (saved / target.name).chmod(0o600)
        created = []
        try:
            # Policy is installed last, only after the protected payload and helper exist.
            for target, contents, mode in (
                (HELPER, (destination / 'aoc-maintain.py').read_bytes(), 0o755),
                (CONFIG, (json.dumps(config, indent=2) + '\n').encode(), 0o600),
                (POLICY, policy.read_bytes(), 0o440),
            ):
                if old:
                    replace_file(target, contents, mode)
                    continue
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
                created.append(target)
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(contents)
                os.chmod(target, mode)
            check_policy(POLICY)
        except Exception:
            if old:
                for target, (contents, mode) in old.items():
                    replace_file(target, contents, mode)
            else:
                for path in reversed(created):
                    path.unlink()
            raise
        return {'installed': True, 'platform': kind, 'account': user,
                'helper': str(HELPER), 'allowed_actions': ACTIONS[kind],
                'services_changed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--replace-approval', help='Explicit previous approval SHA-256; preserves account, role and sudo policy')
    args = parser.parse_args()
    print(json.dumps(install(args.archive, args.sha256, args.user, args.check, args.replace_approval)))
