#!/usr/bin/env python3
"""Stage, verify and install the independent stack; never start or enable it."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stack_runtime', HERE / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
PINNED_OCUDU = '050a2bb72e1d794cd60570d809987c1fcda3e54b'
UNIT_DIR = Path('/etc/systemd/system')
CLI = Path('/usr/local/bin/aoc-v2ctl')
UNIT_NAMES = runtime.UNITS


def files(root, exclude_manifest=True):
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Links and special files are not allowed')
        if path.is_file() and not (exclude_manifest and path == root / 'release.json'):
            result[str(path.relative_to(root))] = runtime.digest(path)
    return result


def units():
    return {name: (HERE / 'systemd' / name).read_text() for name in UNIT_NAMES}


def check_core(core):
    value = json.loads((core / 'bundle.json').read_text())
    runtime.verify_tree(core, value['files'])
    if files(core, exclude_manifest=False) != {**value['files'], 'bundle.json': runtime.digest(core / 'bundle.json')}:
        raise ValueError('Unlisted core bundle files')
    if (value.get('project') != runtime.PROJECT or not value.get('database_auth')
            or not value.get('n6') or value.get('subnet') != '172.28.81.0/24'):
        raise ValueError('Authenticated N6 bundle for the supported project/subnet required')
    compose = json.loads((core / 'compose.json').read_text())
    expected = {'mongo', 'nrf', 'amf', 'smf', 'upf', 'udr', 'udm', 'ausf', 'pcf', 'nssf', 'bsf', 'ext-dn'}
    if set(compose['services']) != expected or set(value['addresses']) != expected:
        raise ValueError('Unexpected core service membership')
    for name, service in compose['services'].items():
        if (service['image'] not in value['images'].values()
                or service['labels'].get('org.agentic-ocudu.owner') != runtime.PROJECT
                or service['networks']['core']['ipv4_address'] != value['addresses'][name]):
            raise ValueError('Core service ownership, address or image mismatch')
    return value


def check_elf(path):
    with path.open('rb') as stream:
        header = stream.read(20)
    if (header[:6] != b'\x7fELF\x02\x01' or len(header) != 20
            or int.from_bytes(header[18:20], 'little') != 183):
        raise ValueError('Expected an ARM64 little-endian ELF executable')


def verify(root):
    if root.is_symlink():
        raise ValueError('Release cannot be a symlink')
    release = json.loads((root / 'release.json').read_text())
    runtime.verify_tree(root, release['files'])
    actual = files(root)
    required = {'runtime.py', 'package.py', 'aocctl', 'bin/gnb', 'bin/probe-b210',
                'core/bundle.json', *('systemd/' + name for name in UNIT_NAMES)}
    if not required.issubset(actual) or actual != release['files']:
        raise ValueError('Incomplete release or unlisted files')
    if (release.get('source_commit') != PINNED_OCUDU or release.get('architecture') != 'aarch64'
            or release.get('release_id') != hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()[:16]):
        raise ValueError('Invalid release provenance')
    check_core(root / 'core')
    for name in ('gnb', 'probe-b210'):
        check_elf(root / 'bin' / name)
    return release


def stage(core, binary, probe, build_record, output):
    # Private deployment input is preserved, never rendered from a live database.
    check_core(core)
    build = json.loads(build_record.read_text())
    if (build.get('commit') != PINNED_OCUDU or build.get('architecture') != 'aarch64'
            or build.get('sha256') != runtime.digest(binary)):
        raise ValueError('Binary does not match the pinned ARM64 build record')
    for path in (binary, probe):
        if path.is_symlink():
            raise ValueError('Executable input cannot be a symlink')
        check_elf(path)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        shutil.copytree(core, output / 'core')
        (output / 'bin').mkdir()
        for source, name in ((binary, 'gnb'), (probe, 'probe-b210')):
            shutil.copyfile(source, output / 'bin' / name)
            (output / 'bin' / name).chmod(0o755)
        for name in ('runtime.py', 'package.py'):
            shutil.copyfile(HERE / name, output / name)
        (output / 'systemd').mkdir()
        for name, content in units().items():
            (output / 'systemd' / name).write_text(content)
        (output / 'aocctl').write_text('#!/bin/sh\nexec /usr/bin/python3 -I /opt/agentic-ocudu/v2/runtime.py "$@"\n')
        (output / 'aocctl').chmod(0o755)
        entries = files(output)
        release = dict(schema_version=3, source_commit=PINNED_OCUDU, architecture='aarch64',
                       rf_accepted=False, files=entries,
                       release_id=hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()[:16])
        (output / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
        verify(output)
        return release
    except Exception:
        shutil.rmtree(output)
        raise


def install(source):
    if os.geteuid() != 0 or platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise ValueError('Installation requires an ARM64 Linux administrator')
    verify(source)
    destinations = [runtime.BASE, CLI, *(UNIT_DIR / name for name in UNIT_NAMES)]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError('Existing release or service found; refusing to overwrite')
    # Copy to root-owned private storage, then verify the copy before installing.
    runtime.BASE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stack-stage-', dir=runtime.BASE.parent) as temporary:
        protected = Path(temporary) / 'release'
        shutil.copytree(source, protected, symlinks=True)
        verify(protected)
        for path in (protected, *protected.rglob('*')):
            os.chown(path, 0, 0)
            # File bind mounts must remain readable by non-root NF/Mongo users.
            # Private 0700 host directories protect their configuration/secrets.
            path.chmod(0o700 if path.is_dir() else 0o755 if path.parent.name == 'bin' or path.name == 'aocctl' else 0o644)
        spec = check_core(protected / 'core')
        # Fail before installing files if artifacts or provisioned database are absent.
        old_core = runtime.CORE
        try:
            runtime.CORE = protected / 'core'
            runtime.resources(spec)
        finally:
            runtime.CORE = old_core
        if runtime.containers():
            raise ValueError('Stop owned containers before installation')
        checks = Path(temporary) / 'unit-check'
        checks.mkdir()
        for name in UNIT_NAMES:
            if runtime.run(['systemctl', 'show', name, '-p', 'LoadState', '--value']).strip() != 'not-found':
                raise ValueError('An existing stack unit must not be replaced')
            (checks / name).write_text((protected / 'systemd' / name).read_text().replace(str(runtime.BASE), str(protected)))
        runtime.run(['systemd-analyze', 'verify', *(str(checks / name) for name in UNIT_NAMES)])
        installed = []
        try:
            protected.rename(runtime.BASE)
            installed.append(runtime.BASE)
            for name in UNIT_NAMES:
                target = UNIT_DIR / name
                with target.open('x') as stream:
                    installed.append(target)
                    stream.write((runtime.BASE / 'systemd' / name).read_text())
                target.chmod(0o644)
            CLI.symlink_to(runtime.BASE / 'aocctl')
            installed.append(CLI)
            runtime.run(['systemctl', 'daemon-reload'])
        except Exception:
            for path in reversed(installed):
                shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()
            runtime.run(['systemctl', 'daemon-reload'])
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    staging = sub.add_parser('stage')
    for name in ('core', 'binary', 'probe', 'build-record', 'output'):
        staging.add_argument('--' + name, type=Path, required=True)
    for name in ('verify', 'install'):
        sub.add_parser(name).add_argument('--source', type=Path, required=True)
    args = vars(parser.parse_args())
    action = args.pop('action')
    if action == 'stage':
        result = stage(**args)
        print(json.dumps({'release_id': result['release_id'], 'rf_accepted': False}))
    elif action == 'verify':
        result = verify(args['source'])
        print(json.dumps({'verified': True, 'release_id': result['release_id']}))
    else:
        install(args['source'])
        print('Installed; services remain stopped and are not enabled at boot')


if __name__ == '__main__':
    main()
