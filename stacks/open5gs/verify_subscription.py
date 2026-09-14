#!/usr/bin/env python3
"""Exercise authenticated insert/refusal with synthetic material in network=none MongoDB."""
import argparse
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

IMAGE = 'sha256:1656dea786dde37f1708fdc7a7c734868648c98803a1d03e9a544aa9e16a1c59'
spec = importlib.util.spec_from_file_location('subscriber', Path(__file__).with_name('subscriber.py'))
subscriber = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subscriber)


def run(argv, stdin=None, timeout=30):
    return subprocess.run(argv, input=stdin, text=True, capture_output=True, timeout=timeout)


def verify(output):
    if output.exists():
        raise ValueError('Result already exists')
    name = 'aoc-v2-subcheck-' + uuid.uuid4().hex[:12]
    result = {'scope': 'synthetic-subscriber-network-none', 'at': time.time(), 'passed': False}
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE], text=True))[0]
    if info['Id'] != IMAGE or info['Architecture'] != 'arm64':
        raise ValueError('Wrong MongoDB image')
    with tempfile.TemporaryDirectory(prefix='aoc-subcheck-') as temp:
        credentials = {'username': 'aoc_subscriber', 'password': secrets.token_hex(24)}
        secret = Path(temp) / 'credentials.json'
        secret.write_text(json.dumps(credentials))
        # Disposable synthetic credential, file-mounted into a network=none container.
        secret.chmod(0o644)
        created = run(['docker', 'create', '--name', name, '--label', 'org.agentic-ocudu.owner=' + name,
                       '--network', 'none', '--user', 'mongodb', '--cap-drop', 'ALL',
                       '--security-opt', 'no-new-privileges', '--memory', '1g', '--cpus', '1',
                       '--mount', 'type=bind,source=' + str(secret) + ',target=/run/secrets/subscriber-db.json,readonly',
                       '--tmpfs', '/data/db:rw,mode=1777', '--entrypoint', 'mongod', IMAGE,
                       '--auth', '--bind_ip', '127.0.0.1', '--port', '27017'])
        if created.returncode:
            raise RuntimeError('Cannot create isolated subscriber test')
        shell = ['docker', 'exec', '-i', name, 'mongosh', '--quiet', '--file', '/dev/stdin']
        try:
            if run(['docker', 'start', name]).returncode:
                raise RuntimeError('Cannot start test database')
            deadline = time.monotonic() + 30
            while True:
                check = run(shell, "quit(db.adminCommand({ping:1}).ok === 1 ? 0 : 1);", timeout=5)
                if check.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('MongoDB readiness timeout')
                time.sleep(0.5)
            admin = secrets.token_hex(24)
            bootstrap = '''try {
const admin = db.getSiblingDB('admin');
admin.createUser({user:'bootstrap',pwd:''' + json.dumps(admin) + ''',roles:['root']});
admin.auth('bootstrap', ''' + json.dumps(admin) + ''');
const credential = ''' + json.dumps(credentials) + ''';
db.getSiblingDB('open5gs').createUser({user:credential.username,pwd:credential.password,
 roles:[{role:'readWrite',db:'open5gs'}]});
print('AUTH_READY');
} catch (_) { quit(1); }
'''
            boot = run(shell, bootstrap)
            if boot.returncode or 'AUTH_READY' not in boot.stdout:
                raise RuntimeError('Database credential initialization failed')
            denied = run(shell, "try { db.getSiblingDB('open5gs').subscribers.countDocuments({}); quit(1); } catch (_) { quit(0); }")
            if denied.returncode:
                raise RuntimeError('Unauthenticated subscription read was not denied')
            result['unauthenticated_read_denied'] = True
            material = {'imsi': '460030000000001', 'ki': '00' * 16, 'opc': '11' * 16,
                        'amf': '8000', 'sqn': 'ffffffffffff'}
            script = subscriber.insert_script(subscriber.document(material))
            inserted = run(shell, script)
            if inserted.returncode:
                raise RuntimeError('Synthetic insert/readback failed')
            result['insert'] = json.loads(inserted.stdout.strip())
            auth = "const c=JSON.parse(require('fs').readFileSync('/run/secrets/subscriber-db.json','utf8')); const core=db.getSiblingDB('open5gs');core.auth(c.username,c.password);"
            advance = run(shell, auth + "core.subscribers.updateOne({imsi:'460030000000001'},{$set:{'security.sqn':NumberLong(42)}});print('ADVANCED');")
            if advance.returncode or 'ADVANCED' not in advance.stdout:
                raise RuntimeError('Synthetic SQN setup failed')
            again = run(shell, script)
            if again.returncode != 2 or json.loads(again.stdout.strip()).get('reason') != 'already_exists':
                raise RuntimeError('Duplicate subscription not rejected')
            proof = run(shell, auth + "const d=core.subscribers.findOne({imsi:'460030000000001'});print(JSON.stringify({count:core.subscribers.countDocuments({}),sqn:d.security.sqn.toString(),bson64:d.security.sqn._bsontype==='Long'}));")
            if proof.returncode:
                raise RuntimeError('SQN preservation query failed')
            result['preservation'] = json.loads(proof.stdout.strip())
            if result['preservation'] != {'count': 1, 'sqn': '42', 'bson64': True}:
                raise RuntimeError('SQN or unique subscription changed')
            result['passed'] = True
        except Exception as error:
            result['error'] = str(error)
        finally:
            stop = run(['docker', 'stop', '--time', '15', name])
            state = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]['State']
            result['exit_code'] = state['ExitCode']
            result['oom'] = state['OOMKilled']
            removed = run(['docker', 'rm', name])
            result['removed'] = removed.returncode == 0
            if stop.returncode or state['ExitCode'] != 0 or state['OOMKilled'] or not result['removed']:
                result['passed'] = False
            output.write_text(json.dumps(result, indent=2) + '\n')
            output.chmod(0o600)
    print(json.dumps(result))
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.output) else 1)
