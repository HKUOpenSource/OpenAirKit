"""Install or roll back the scoped radio preflight fix while the new stack is stopped."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

INSTALL = Path('/opt/agentic-ocudu')
UNIT_DIR = Path('/etc/systemd/system')
BASE = {
    'scripts/aoclib/preflight.py': '0c724593e841adcef0edadd0f1800e058e1767087bb15e14bd51b217c931544e',
    'scripts/radio_runtime.py': 'f6e83da81ddc49cfb8cbd41b8ab0025f0321e69d7ae07eae8c7c34dd371e5443',
}
UNITS = ('aoc-stack.target', 'aoc-core.service', 'aoc-gnb.service')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(argv):
    subprocess.run(argv, check=True, timeout=30)


def atomic(path, body):
    pending = path.with_name(path.name + '.preflight-next')
    with pending.open('x') as handle:
        handle.write(body)
    pending.chmod(0o644)
    os.replace(pending, path)


def pointer(release):
    pending = INSTALL / '.current-preflight-next'
    pending.symlink_to(release)
    os.replace(pending, INSTALL / 'current')


def verify(package):
    manifest = json.loads((package / 'manifest.json').read_text())
    expected = set(BASE) | {'repair_radio_preflight.py'}
    if set(manifest['files']) != expected:
        raise ValueError('Unexpected repair payload')
    for name, digest in manifest['files'].items():
        path = package / name
        if path.is_symlink() or sha(path) != digest:
            raise ValueError('Repair checksum differs: ' + name)
    return manifest


def stage(output):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    for name in BASE:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    shutil.copyfile(Path(__file__), output / 'repair_radio_preflight.py')
    files = {name: sha(output / name) for name in (*BASE, 'repair_radio_preflight.py')}
    (output / 'manifest.json').write_text(json.dumps({'files': files}, indent=2) + '\n')
    print(json.dumps(verify(output)))


def stopped(runtime):
    for unit in UNITS:
        state = runtime.show(unit)
        if state.get('ActiveState') not in ('inactive', 'failed') or int(state.get('MainPID', 0)):
            raise ValueError('Stop the new stack before repairing: ' + unit)


def restore(saved):
    previous = Path(saved['previous'])
    if previous.parent != INSTALL / 'releases' or not previous.is_dir():
        raise ValueError('Previous release is unavailable')
    if set(saved['units']) != set(UNITS):
        raise ValueError('Unexpected saved units')
    for name, body in saved['units'].items():
        atomic(UNIT_DIR / name, body)
    pointer(previous)
    call(['systemctl', 'daemon-reload'])


def install(runtime, package):
    payload = verify(package)
    current = (INSTALL / 'current').resolve(strict=True)
    runtime.verify_release()
    with runtime.switch_lock():
        stopped(runtime)
        if (current / 'preflight-fix.json').exists():
            if all(sha(current / name) == payload['files'][name] for name in BASE):
                print('Preflight fix already installed; no services started')
                return
            raise ValueError('A different preflight fix is already installed')
        for name, expected in BASE.items():
            if sha(current / name) != expected:
                raise ValueError('Unsupported installed baseline: ' + name)
        manifest = json.loads((current / 'release.json').read_text())
        if set(manifest['units']) != set(UNITS):
            raise ValueError('This package requires the reviewed three-unit radio release')
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        release = INSTALL / 'releases' / ('preflight-' + fingerprint)
        shutil.copytree(current, release, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in BASE:
            shutil.copyfile(package / name, release / name)
            (release / name).chmod(0o644)
        saved = {'previous': str(current), 'units': {name: (UNIT_DIR / name).read_text() for name in UNITS}}
        (release / 'preflight-fix.json').write_text(json.dumps(saved, indent=2))
        rendered = {name: body.replace(str(current), str(release)) for name, body in saved['units'].items()}
        candidate = release / 'preflight-units'
        candidate.mkdir()
        for name, body in rendered.items():
            (candidate / name).write_text(body)
        call(['systemd-analyze', 'verify', *[str(candidate / name) for name in UNITS]])
        manifest['release_id'] = release.name
        manifest['files'] = {str(p.relative_to(release)): sha(p) for p in release.rglob('*')
                             if p.is_file() and p != release / 'release.json'}
        manifest['units'] = {name: hashlib.sha256(body.encode()).hexdigest() for name, body in rendered.items()}
        (release / 'release.json').write_text(json.dumps(manifest, indent=2))
        try:
            for name, body in rendered.items():
                atomic(UNIT_DIR / name, body)
            pointer(release)
            call(['systemctl', 'daemon-reload'])
        except BaseException:
            restore(saved)
            raise
    print('Installed ' + release.name + '; monitor unchanged; no services started')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('stage', 'verify', 'install', 'rollback'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'stage':
        if not args.output:
            parser.error('stage requires --output')
        stage(args.output)
        return
    package = Path(__file__).resolve().parent
    verify(package)
    if args.action == 'verify':
        print('Preflight repair package verified')
        return
    if os.geteuid() != 0:
        raise SystemExit('Run install/rollback in the Spark sudo terminal')
    os.umask(0o022)
    current = (INSTALL / 'current').resolve(strict=True)
    if current.parent != INSTALL / 'releases' or current.stat().st_uid != 0 or current.stat().st_mode & 0o022:
        raise ValueError('Unexpected current release ownership')
    spec = importlib.util.spec_from_file_location('aoc_repair_runtime', current / 'scripts/radio_runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    if args.action == 'install':
        install(runtime, package)
    else:
        runtime.verify_release()
        with runtime.switch_lock():
            stopped(runtime)
            restore(json.loads((current / 'preflight-fix.json').read_text()))
        print('Previous radio release restored; no services started')


if __name__ == '__main__':
    main()
