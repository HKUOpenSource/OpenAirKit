#!/usr/bin/env python3
"""One-time repair of the reviewed ext-DN upgrade's outer release checksums."""
import copy
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time

BASE = Path('/opt/agentic-ocudu/v2')
LOCK = Path('/var/lib/aoc-maintenance/operation.lock')
FILES = ('runtime.py', 'compose.json', 'bundle.json')
RUNTIME_SHA = '6ceb5eae5b4358e586babeb6e23ec4995cd997a7b54455d565492e10abda0d55'
IMAGE = 'sha256:45fc43f140364eab399b351d5672e9501279669acf2d9420360f8d28a2f87d31'


def secure(path):
    for item in (path, *path.parents):
        info = item.lstat()
        if (info.st_uid != 0 or info.st_mode & 0o022
                or not (stat.S_ISREG(info.st_mode) if item == path else stat.S_ISDIR(info.st_mode))):
            raise ValueError('Unsafe repair input: %s (uid=%d gid=%d mode=%04o type=%o)' %
                             (item, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
                              stat.S_IFMT(info.st_mode)))
    return path


def digest(path):
    return hashlib.sha256(secure(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(secure(path).read_bytes())


def child(root, name):
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Unsafe manifest entry')
    return root / name


def verified_update(base):
    """Only accept the exact reviewed delta from an intact pre-upgrade backup."""
    release = read(base / 'release.json')
    changed = {'core/' + name for name in FILES}
    if not changed <= set(release['files']):
        raise ValueError('Incomplete parent ownership record')
    for name, expected in release['files'].items():
        if name not in changed and digest(child(base, name)) != expected:
            raise ValueError('Unrelated release change: ' + name)
    matches = []
    for backup in base.glob('connectivity-backup-*'):
        if all(digest(backup / name) == release['files']['core/' + name] for name in FILES):
            matches.append(backup)
    if not matches:
        raise ValueError('No intact backup matches the original release')
    backup = sorted(matches)[0]
    core = base / 'core'
    if digest(core / 'runtime.py') != RUNTIME_SHA:
        raise ValueError('Runtime differs from reviewed connectivity code')
    previous_compose = read(backup / 'compose.json')
    expected_compose = copy.deepcopy(previous_compose)
    expected_compose['services']['ext-dn']['image'] = IMAGE
    if read(core / 'compose.json') != expected_compose:
        raise ValueError('Compose differs beyond the approved ext-DN image change')
    expected_bundle = read(backup / 'bundle.json')
    expected_bundle['images']['connectivity'] = IMAGE
    for name in ('runtime.py', 'compose.json'):
        expected_bundle['files'][name] = digest(core / name)
    current_bundle = read(core / 'bundle.json')
    if current_bundle != expected_bundle or current_bundle.get('project') != 'aoc-v2-open5gs':
        raise ValueError('Bundle differs beyond the reviewed connectivity change')
    for name, expected in current_bundle['files'].items():
        if digest(child(core, name)) != expected:
            raise ValueError('Core integrity failed: ' + name)
    updated = copy.deepcopy(release)
    for name in FILES:
        updated['files']['core/' + name] = digest(core / name)
    return updated


def atomic(path, data):
    fd, pending = tempfile.mkstemp(prefix='.connectivity-repair-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        Path(pending).unlink(missing_ok=True)


def directory_repairs(base):
    # The old installer chowned all directories but preserved their staging
    # modes. A root:root 0775 child can exist inside the private 0700 release.
    # Tighten those directories; never weaken secure() or accept writable code.
    release = read(base / 'release.json')
    if stat.S_IMODE(base.lstat().st_mode) != 0o700:
        raise ValueError('Directory repair requires the private 0700 release root')
    directories = set()
    for name in release['files']:
        source = child(base, name)
        for parent in source.parents:
            if parent == base:
                break
            if not parent.is_relative_to(base):
                raise ValueError('Manifest path escapes the release')
            directories.add(parent)
    changes = []
    # Check ancestors before inspecting descendants; never traverse a symlink.
    for directory in sorted(directories, key=lambda p: (len(p.parts), str(p))):
        info = directory.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or mode & 0o002):
            raise ValueError('Unexpected installed directory: %s (uid=%d gid=%d mode=%04o type=%o)' %
                             (directory, info.st_uid, info.st_gid, mode, stat.S_IFMT(info.st_mode)))
        if mode & 0o020:
            changes.append((directory, mode))
    return changes


@contextmanager
def protected_directories(base):
    changes = directory_repairs(base)
    applied = []
    try:
        for directory, mode in changes:
            directory.chmod(mode & ~0o022)
            applied.append((directory, mode))
        yield changes
    except BaseException:
        for directory, mode in reversed(applied):
            directory.chmod(mode)
        raise


def repair_manifest(base, permissions):
    updated = verified_update(base)
    target = base / 'release.json'
    original = secure(target).read_bytes()
    backup = base / ('release.json.connectivity-before-' + str(time.time_ns()))
    with backup.open('xb') as stream:
        stream.write(original)
    backup.chmod(0o600)
    if permissions:
        receipt = backup.with_name(backup.name + '.permissions.json')
        with receipt.open('x') as stream:
            json.dump({str(path.relative_to(base)): {'before': mode, 'after': mode & ~0o022}
                       for path, mode in permissions}, stream)
        receipt.chmod(0o600)
    try:
        atomic(target, (json.dumps(updated, indent=2) + '\n').encode())
        for name, expected in read(target)['files'].items():
            if digest(child(base, name)) != expected:
                raise ValueError('Post-repair integrity failed: ' + name)
    except Exception:
        atomic(target, original)
        raise
    return {'repaired': True, 'changed': ['release.json'], 'services_changed': False,
            'directory_permissions_tightened': [str(path.relative_to(base)) for path, _ in permissions],
            'backup': str(backup)}


def repair(base):
    with protected_directories(base) as permissions:
        return repair_manifest(base, permissions)


def main():
    if os.geteuid() != 0:
        raise ValueError('Run the reviewed repair once from an administrator terminal')
    os.umask(0o077)
    with secure(LOCK).open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(['/usr/bin/systemctl', 'show', 'aoc-v2-radio.service',
                                 '-p', 'ActiveState', '-p', 'MainPID', '-p', 'ControlPID'],
                                check=True, text=True, capture_output=True, timeout=15)
        state = dict(line.split('=', 1) for line in result.stdout.splitlines())
        if state.get('ActiveState') not in ('inactive', 'failed') or state.get('MainPID') != '0' or state.get('ControlPID') != '0':
            raise ValueError('Radio must be fully stopped before repairing its manifest')
        print(json.dumps(repair(BASE)))


if __name__ == '__main__':
    main()
