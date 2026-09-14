#!/usr/bin/env python3
"""Enable the V2 OCUDU loopback JSON metrics endpoint as a rollback transaction."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time


BASE = Path('/opt/agentic-ocudu/v2')
STATE = Path('/var/lib/agentic-ocudu/v2')
UNIT = Path('/etc/systemd/system/aoc-v2-radio.service')
DROPIN = Path('/etc/systemd/system/aoc-v2-radio.service.d/metrics.conf')
GUARD = Path('/usr/local/libexec/aoc-v2-metrics-guard')
GUARD_UNIT = Path('/etc/systemd/system/aoc-v2-metrics-guard.service')
DISABLED = b"'remote_control': {'enabled': False},"
ENABLED = b"'remote_control': {'enabled': True, 'bind_addr': '127.0.0.1', 'port': 8001},"
STDOUT_ONLY = b"'metrics': {'autostart_stdout_metrics': True},"
JSON_METRICS = b"'metrics': {'enable_json': True, 'autostart_stdout_metrics': True},"
GUARD_PROGRAM = b'''#!/usr/bin/python3
import os, subprocess
RULES = """table inet aoc_v2_metrics_guard {
 chain output { type filter hook output priority -10; policy accept;
  ip daddr 127.0.0.1 tcp dport 8001 meta skuid != 0 reject
 }
}\n"""
if os.geteuid() != 0: raise SystemExit("root required")
old=subprocess.run(["nft","-nn","list","table","inet","aoc_v2_metrics_guard"],capture_output=True,text=True,timeout=5)
if old.returncode == 0:
    if "tcp dport 8001" not in old.stdout or "skuid != 0 reject" not in old.stdout: raise SystemExit("guard differs")
else:
    subprocess.run(["nft","--check","-f","-"],input=RULES,text=True,check=True,timeout=5)
    subprocess.run(["nft","-f","-"],input=RULES,text=True,check=True,timeout=5)
'''
DROPIN_TEXT = '[Unit]\nRequires=aoc-v2-metrics-guard.service\nAfter=aoc-v2-metrics-guard.service\n'
GUARD_UNIT_TEXT = '''[Unit]
Description=Agentic-OCUDU V2 loopback metrics access guard

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/libexec/aoc-v2-metrics-guard
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_NETLINK AF_UNIX

[Install]
WantedBy=multi-user.target
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transform(runtime):
    if runtime.count(DISABLED) != 1 or ENABLED in runtime:
        raise ValueError('Expected exactly one disabled V2 remote-control block')
    updated = runtime.replace(DISABLED, ENABLED)
    if updated.count(STDOUT_ONLY) == 1:
        updated = updated.replace(STDOUT_ONLY, JSON_METRICS)
    elif JSON_METRICS not in updated:
        updated = updated.replace(ENABLED, ENABLED + b"\n        " + JSON_METRICS)
    if updated.count(JSON_METRICS) != 1:
        raise ValueError('Expected exactly one JSON metrics block')
    compile(updated, 'runtime.py', 'exec')
    return updated


def run(arguments, timeout=360):
    result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed (exit %d): %s' % (result.returncode, ' '.join(arguments[:3])))
    return result.stdout


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.aoc-metrics.tmp')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(mode)
    temporary.replace(path)


def stopped():
    state = run(['systemctl', 'show', 'aoc-v2-radio.service', '-p', 'ActiveState',
                 '-p', 'MainPID', '-p', 'ControlPID'])
    values = dict(line.split('=', 1) for line in state.splitlines())
    return values.get('ActiveState') in ('inactive', 'failed') and values.get('MainPID') == values.get('ControlPID') == '0'


def remove_guard():
    if subprocess.run(['nft', 'list', 'table', 'inet', 'aoc_v2_metrics_guard'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
        run(['nft', 'delete', 'table', 'inet', 'aoc_v2_metrics_guard'], 10)


def restore(backup):
    transaction = json.loads((backup / 'transaction.json').read_text())
    atomic(BASE / 'runtime.py', (backup / 'runtime.py').read_bytes())
    atomic(BASE / 'release.json', (backup / 'release.json').read_bytes())
    for path, name in ((DROPIN, 'metrics.conf'), (GUARD, 'guard'), (GUARD_UNIT, 'guard.service')):
        marker = transaction['existed'][name]
        if marker:
            atomic(path, (backup / name).read_bytes(), 0o755 if path == GUARD else 0o644)
        else:
            path.unlink(missing_ok=True)
    remove_guard()
    run(['systemctl', 'daemon-reload'], 30)


def wait_endpoint():
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', 8001), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError('OCUDU loopback metrics endpoint did not listen')


def install():
    if not UNIT.is_file() or 'ExecStart=/opt/agentic-ocudu/v2/bin/gnb ' not in UNIT.read_text():
        raise ValueError('Unexpected V2 radio unit')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 8001))
    runtime = (BASE / 'runtime.py').read_bytes()
    updated = transform(runtime)
    release = json.loads((BASE / 'release.json').read_text())
    if release['files'].get('runtime.py') != sha(runtime):
        raise ValueError('Installed V2 runtime differs from release manifest')
    release['files']['runtime.py'] = sha(updated)
    release['radio_json_metrics'] = {'version': 1, 'loopback': '127.0.0.1:8001', 'root_only': True}
    encoded_release = (json.dumps(release, indent=2) + '\n').encode()
    backup = STATE / ('radio-json-metrics-' + str(time.time_ns()))
    backup.mkdir(mode=0o700, parents=True)
    shutil.copy2(BASE / 'runtime.py', backup / 'runtime.py')
    shutil.copy2(BASE / 'release.json', backup / 'release.json')
    existed = {}
    for path, name in ((DROPIN, 'metrics.conf'), (GUARD, 'guard'), (GUARD_UNIT, 'guard.service')):
        existed[name] = path.exists()
        if path.exists():
            shutil.copy2(path, backup / name)
    (backup / 'transaction.json').write_text(json.dumps({
        'before_runtime': sha(runtime), 'after_runtime': sha(updated), 'existed': existed}, indent=2) + '\n')
    run(['systemctl', 'stop', 'aoc-v2-radio.service'])
    if not stopped():
        raise RuntimeError('V2 radio did not stop cleanly')
    try:
        atomic(BASE / 'runtime.py', updated)
        atomic(BASE / 'release.json', encoded_release)
        atomic(GUARD, GUARD_PROGRAM, 0o755)
        atomic(GUARD_UNIT, GUARD_UNIT_TEXT.encode())
        atomic(DROPIN, DROPIN_TEXT.encode())
        run(['systemctl', 'daemon-reload'], 30)
        run(['systemctl', 'start', 'aoc-v2-radio.service'])
        wait_endpoint()
    except Exception:
        if not stopped():
            run(['systemctl', 'stop', 'aoc-v2-radio.service'])
        restore(backup)
        run(['systemctl', 'start', 'aoc-v2-radio.service'])
        raise
    print(json.dumps({'installed': True, 'backup': str(backup), 'listen': '127.0.0.1:8001',
                      'access': 'root-only-loopback', 'radio_restarted': True}))


def rollback(name):
    if not re.fullmatch(r'radio-json-metrics-[0-9]+', name):
        raise ValueError('Invalid metrics backup name')
    backup = STATE / name
    transaction = json.loads((backup / 'transaction.json').read_text())
    if sha((BASE / 'runtime.py').read_bytes()) != transaction['after_runtime']:
        raise ValueError('Installed runtime changed after metrics transaction')
    run(['systemctl', 'stop', 'aoc-v2-radio.service'])
    if not stopped():
        raise RuntimeError('V2 radio did not stop cleanly')
    restore(backup)
    run(['systemctl', 'start', 'aoc-v2-radio.service'])
    print(json.dumps({'rolled_back': True, 'backup': name, 'radio_restarted': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('install')
    sub.add_parser('rollback').add_argument('backup_name')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run in the Spark sudo terminal')
    os.umask(0o077)
    with open('/run/lock/aoc-v2-stack.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install() if args.action == 'install' else rollback(args.backup_name)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('AOC V2 METRICS ERROR: ' + str(error))
        raise SystemExit(1)
