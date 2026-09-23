#!/usr/bin/env python3
"""Upgrade only the owned ext-DN service, preserving subscriber and NF configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

FILES = ('runtime.py', 'compose.json', 'bundle.json')


def parent_release(bundle):
    path = bundle.parent / 'release.json'
    if not path.exists():
        return None
    if path.is_symlink() or bundle.name != 'core':
        raise ValueError('Unexpected parent release layout')
    release = json.loads(path.read_text())
    if not {'core/' + name for name in FILES} <= set(release['files']):
        raise ValueError('Parent release does not own all upgraded files')
    for name, expected in release['files'].items():
        source = bundle.parent / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or source.is_symlink()
                or not source.resolve().is_relative_to(bundle.parent)
                or hashlib.sha256(source.read_bytes()).hexdigest() != expected):
            raise ValueError('Parent release integrity failed: ' + name)
    return release


def run(argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT, timeout=90)


def verify(bundle):
    manifest = json.loads((bundle / 'bundle.json').read_text())
    compose = json.loads((bundle / 'compose.json').read_text())
    if manifest.get('project') != 'aoc-v2-open5gs' or compose.get('name') != manifest['project']:
        raise ValueError('Not the owned Open5GS bundle')
    for name, expected in manifest['files'].items():
        path = bundle / name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle):
            raise ValueError('Unsafe bundle path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Bundle changed; reconcile its manifest before upgrading')
    service = compose['services']['ext-dn']
    if service.get('ports') or service.get('network_mode') or service.get('privileged'):
        raise ValueError('Unexpected external data network exposure')
    if service.get('entrypoint') != ['python3', '/opt/aoc/runtime.py']:
        raise ValueError('Unexpected ext-DN entrypoint')
    if service.get('command') != ['run', 'ext-dn', manifest['addresses']['ext-dn']]:
        raise ValueError('Unexpected ext-DN command')
    return manifest, compose


def write(path, data):
    temporary = path.with_name('.' + path.name + '.upgrade')
    with temporary.open('xb') as output:
        output.write(data)
    temporary.chmod(0o644 if path.name == 'runtime.py' else 0o600)
    temporary.replace(path)


def recreate(bundle):
    command = ['docker', 'compose', '--project-name', 'aoc-v2-open5gs',
               '--project-directory', str(bundle), '-f', str(bundle / 'compose.json')]
    run([*command, 'up', '-d', '--no-deps', '--force-recreate', '--wait',
         '--wait-timeout', '60', 'ext-dn'])
    run([*command, 'exec', '-T', 'ext-dn', 'python3', '/opt/aoc/runtime.py',
         'health', 'ext-dn', json.loads((bundle / 'bundle.json').read_text())['addresses']['ext-dn']])


def upgrade(bundle):
    bundle = bundle.resolve()
    manifest, compose = verify(bundle)
    release = parent_release(bundle)
    lock = json.loads((Path(__file__).resolve().parents[1] / 'artifacts.lock.json').read_text())
    image = lock['connectivity_runtime']['image_id']
    info = json.loads(run(['docker', 'image', 'inspect', image]))[0]
    if info['Id'] != image or info['Architecture'] != 'arm64':
        raise ValueError('Pinned connectivity image is unavailable')
    backup = bundle.parent / ('connectivity-backup-' + str(time.time_ns()))
    backup.mkdir(mode=0o700)
    for name in FILES:
        shutil.copyfile(bundle / name, backup / name)
        (backup / name).chmod(0o600)
    if release is not None:
        shutil.copyfile(bundle.parent / 'release.json', backup / 'release.json')
        (backup / 'release.json').chmod(0o600)
    try:
        compose['services']['ext-dn']['image'] = image
        manifest['images']['connectivity'] = image
        write(bundle / 'runtime.py', Path(__file__).with_name('runtime.py').read_bytes())
        write(bundle / 'compose.json', (json.dumps(compose, indent=2) + '\n').encode())
        for name in ('runtime.py', 'compose.json'):
            manifest['files'][name] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        write(bundle / 'bundle.json', (json.dumps(manifest, indent=2) + '\n').encode())
        if release is not None:
            for name in FILES:
                release['files']['core/' + name] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
            write(bundle.parent / 'release.json', (json.dumps(release, indent=2) + '\n').encode())
            parent_release(bundle)
        recreate(bundle)
    except Exception:
        for name in FILES:
            write(bundle / name, (backup / name).read_bytes())
        if release is not None:
            write(bundle.parent / 'release.json', (backup / 'release.json').read_bytes())
        recreate(bundle)
        raise
    return {'upgraded': True, 'backup': str(backup), 'image': image,
            'scope': 'ext-dn only; subscriber database and other services unchanged'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(upgrade(args.bundle)))
