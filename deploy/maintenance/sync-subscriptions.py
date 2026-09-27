#!/usr/bin/env python3
"""One-time, insert-only OAI to Open5GS subscription transfer on the core host.

Run --check-source unprivileged first. --apply requires terminal sudo. Never
prints identities, keys, database diagnostics or configuration contents.
"""
import argparse
import fcntl
import gzip
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

PROJECT = 'aoc-v2-open5gs'
VOLUME = PROJECT + '-mongo'
NETWORK = PROJECT + '-core'
BUNDLE = Path('/opt/agentic-ocudu/v2/core')
MONGO_IMAGE = 'sha256:1656dea786dde37f1708fdc7a7c734868648c98803a1d03e9a544aa9e16a1c59'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
AUTH = """const core=db.getSiblingDB('open5gs');
const c=JSON.parse(require('fs').readFileSync('/run/secrets/subscriber-db.json','utf8'));
if(!core.auth(c.username,c.password)) throw new Error('auth');
"""


class Refused(RuntimeError):
    pass


def run(argv, stdin=None, timeout=60):
    value = subprocess.run(argv, input=stdin, text=True, capture_output=True,
                           timeout=timeout, env=ENV)
    if value.returncode:
        raise Refused('A bounded command failed; sensitive output withheld')
    return value.stdout


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def private_json(path, value):
    with path.open('x') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def subscriber_module():
    path = Path(__file__).with_name('subscriber.py')
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / 'stacks/open5gs/subscriber.py'
    spec = importlib.util.spec_from_file_location('subscription_document', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source():
    info = json.loads(run(['docker', 'inspect', 'mysql']))[0]
    if (info['Config']['Labels'].get('com.docker.compose.project') != 'oai-only-cn5g'
            or not info['State']['Running']):
        raise Refused('Source database ownership or state differs')
    query = """START TRANSACTION READ ONLY;
SELECT JSON_OBJECT('imsi',a.ueid,'ki',a.encPermanentKey,'opc',a.encOpcKey,
'amf',a.authenticationManagementField,'method',a.authenticationMethod,
'algorithm',a.algorithmId,'access',
(SELECT COUNT(*) FROM AccessAndMobilitySubscriptionData b
 WHERE b.ueid=a.ueid AND b.servingPlmnid='46003'), 'data',
(SELECT COUNT(*) FROM SessionManagementSubscriptionData s
 WHERE s.ueid=a.ueid AND s.servingPlmnid='46003'
 AND JSON_CONTAINS_PATH(s.dnnConfigurations,'one','$.oai')))
FROM AuthenticationSubscription a ORDER BY a.ueid;
COMMIT;"""
    raw = run(['docker', 'exec', '-i', 'mysql', 'sh', '-c',
               'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -u root oai_db -N -B'], query)
    module = subscriber_module()
    documents = []
    for row in raw.splitlines():
        item = json.loads(row)
        if (item.pop('method') != '5G_AKA' or item.pop('algorithm') != 'milenage'
                or item.pop('access') != 1 or item.pop('data') != 1):
            raise Refused('A source subscription has an unsupported or incomplete profile')
        documents.append(module.document(item))
    if not documents or len({d['imsi'] for d in documents}) != len(documents):
        raise Refused('Source is empty or contains duplicate identities')
    return documents


def plan(candidates, existing):
    by_id = {d['imsi']: d for d in existing}
    if len(by_id) != len(existing):
        raise Refused('Target contains duplicate identities')
    missing = []
    for doc in candidates:
        old = by_id.get(doc['imsi'])
        if old is None:
            missing.append(doc)
            continue
        security = old.get('security', {})
        if any(str(security.get(k, '')).lower() != doc['security'][k]
               for k in ('k', 'opc', 'amf')) or security.get('op') not in (None, ''):
            raise Refused('Existing static authentication conflicts; nothing overwritten')
    return missing


def unchanged(before, after):
    current = {d['imsi']: d for d in after}
    return all(current.get(d['imsi']) == d for d in before)


def normalize_int32(value):
    # Canonical EJSON wraps ordinary fields as int32; keep int64 SQN typed.
    if isinstance(value, dict):
        if set(value) == {'$numberInt'}:
            return int(value['$numberInt'])
        return {k: normalize_int32(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_int32(v) for v in value]
    return value


def stopped():
    for unit in ('aoc-v2-core.service', 'aoc-v2-radio.service'):
        raw = run(['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'MainPID', '-p', 'ControlPID'])
        state = dict(line.split('=', 1) for line in raw.splitlines())
        if (state.get('ActiveState') not in ('inactive', 'failed')
                or state.get('MainPID') != '0' or state.get('ControlPID') != '0'):
            raise Refused('Stop the project core and radio before database maintenance')


def preflight():
    stopped()
    manifest = json.loads((BUNDLE / 'bundle.json').read_text())
    config = json.loads((BUNDLE / 'compose.json').read_text())
    if manifest.get('project') != PROJECT or not manifest.get('database_auth'):
        raise Refused('Wrong target bundle')
    for name, expected in manifest['files'].items():
        path = BUNDLE / name
        if (path.is_symlink() or not path.resolve().is_relative_to(BUNDLE.resolve())
                or digest(path) != expected):
            raise Refused('Target bundle integrity check failed')
    mongo = config['services']['mongo']
    if (config.get('name') != PROJECT or mongo.get('image') != MONGO_IMAGE
            or manifest['images']['mongodb'] != MONGO_IMAGE
            or mongo.get('ports') or mongo.get('network_mode') or mongo.get('privileged')
            or mongo.get('depends_on') or mongo.get('volumes', [])[0] != 'mongo-data:/data/db'
            or config['volumes']['mongo-data']['name'] != VOLUME):
        raise Refused('Unexpected database image, storage or exposure')
    image = json.loads(run(['docker', 'image', 'inspect', MONGO_IMAGE]))[0]
    if image['Architecture'] != 'arm64':
        raise Refused('Wrong database image architecture')
    if run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT]).strip():
        raise Refused('Existing target containers require inspection')
    if run(['docker', 'ps', '-q', '--filter', 'volume=' + VOLUME]).strip():
        raise Refused('Database volume is in use')
    if NETWORK in run(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines():
        raise Refused('Existing target network requires inspection')
    volume = json.loads(run(['docker', 'volume', 'inspect', VOLUME]))[0]
    if (volume.get('Driver') != 'local' or volume.get('Options')
            or volume.get('Labels', {}).get('org.agentic-ocudu.owner') != PROJECT):
        raise Refused('Wrong database volume ownership')
    storage = Path(volume['Mountpoint'])
    if not (storage / 'WiredTiger').is_file():
        raise Refused('Existing database is missing; empty initialization is forbidden')
    subnet = ipaddress.ip_network(manifest['subnet'])
    for route in json.loads(run(['ip', '-j', '-4', 'route', 'show', 'table', 'all'])):
        if route.get('dst', 'default') != 'default' and subnet.overlaps(ipaddress.ip_network(route['dst'], strict=False)):
            raise Refused('Database network overlaps an existing host route')
    ids = run(['docker', 'network', 'ls', '-q']).split()
    for network in json.loads(run(['docker', 'network', 'inspect', *ids])) if ids else []:
        for entry in network.get('IPAM', {}).get('Config') or []:
            if entry.get('Subnet') and ':' not in entry['Subnet'] and subnet.overlaps(ipaddress.ip_network(entry['Subnet'])):
                raise Refused('Database network overlaps an existing Docker network')
    compose = ['docker', 'compose', '--project-name', PROJECT, '--project-directory', str(BUNDLE),
               '-f', str(BUNDLE / 'compose.json')]
    run([*compose, 'config', '--quiet'])
    return manifest, compose, storage


def snapshot(shell):
    payload = run(shell, 'try {' + AUTH + """
const indexes=core.subscribers.getIndexes();
if(!indexes.some(i=>i.unique===true && Object.keys(i.key).length===1 && i.key.imsi===1))
 throw new Error('unique index missing');
print(EJSON.stringify(core.subscribers.find({}).sort({imsi:1}).toArray(), {relaxed:false}));
} catch (_) { quit(1); }""")
    return json.loads(payload)


def apply(expected_count):
    os.umask(0o077)
    lock_fd = os.open('/var/lib/aoc-maintenance/operation.lock', os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(lock_fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        candidates = source()
        if len(candidates) != expected_count:
            raise Refused('Source count changed; review the scope again')
        manifest, compose, storage = preflight()
        directory = Path('/var/lib/aoc-maintenance') / ('subscription-sync-' + str(time.time_ns()))
        directory.mkdir(mode=0o700)
        result = {'scope': 'insert-only-static-subscriptions', 'passed': False,
                  'source_count': len(candidates), 'inserted': 0, 'cleanup': False,
                  'bundle_sha256': digest(BUNDLE / 'bundle.json'), 'backup': str(directory)}
        archive = directory / 'mongo-volume-before.tar.gz'
        print('Creating private offline database backup.', flush=True)
        run(['tar', '-czf', str(archive), '-C', str(storage), '.'], timeout=300)
        # Read the full gzip stream to validate CRC, and check the archive directory.
        with gzip.open(archive, 'rb') as stream:
            while stream.read(1024 * 1024):
                pass
        with tarfile.open(archive) as saved:
            if './WiredTiger' not in saved.getnames():
                raise Refused('Offline backup validation failed')
        result['offline_backup_sha256'] = digest(archive)
        private_json(directory / 'backup.json', result)
        attempted_start = False
        try:
            stopped()
            attempted_start = True
            print('Starting only the existing Open5GS database.', flush=True)
            run([*compose, 'up', '-d', '--no-deps', '--pull', 'never', '--wait', '--wait-timeout', '90', 'mongo'], timeout=120)
            ids = run([*compose, 'ps', '-aq', 'mongo']).split()
            if len(ids) != 1:
                raise Refused('Expected one target database container')
            info = json.loads(run(['docker', 'inspect', ids[0]]))[0]
            if (info['Image'] != MONGO_IMAGE or info['Config']['Labels'].get('org.agentic-ocudu.owner') != PROJECT
                    or not any(m.get('Name') == VOLUME and m.get('Destination') == '/data/db' for m in info['Mounts'])):
                raise Refused('Running target ownership differs')
            shell = ['docker', 'exec', '-i', ids[0], 'mongosh', '--host', manifest['addresses']['mongo'],
                     '--quiet', '--file', '/dev/stdin']
            before = snapshot(shell)
            if not before:
                raise Refused('Unexpected empty target; inspect before importing')
            private_json(directory / 'subscribers-before.ejson', before)
            missing = plan(candidates, before)
            private_json(directory / 'batch-private.json', {'new_identities': [d['imsi'] for d in missing]})
            result.update(target_before=len(before), planned_new=len(missing), existing_preserved=len(candidates)-len(missing))
            print(json.dumps({k: result[k] for k in ('source_count', 'target_before', 'planned_new', 'existing_preserved')}), flush=True)
            if source() != candidates or snapshot(shell) != before:
                raise Refused('Source static material or target changed before insertion')
            module = subscriber_module()
            for candidate in missing:
                stopped()
                reply = json.loads(run(shell, module.insert_script(candidate)))
                if reply.get('inserted') is not True:
                    raise Refused('Insert acknowledgement missing; do not retry automatically')
                result['inserted'] += 1
                private_json(directory / ('insert-' + str(result['inserted']) + '.json'),
                             {'imsi': candidate['imsi'], 'acknowledged': True})
            after = snapshot(shell)
            if (not unchanged(before, after) or len(after) != len(before) + len(missing)
                    or plan(candidates, after)):
                raise Refused('Final readback differs; preserve state for inspection')
            for candidate in missing:
                saved = next(d for d in after if d['imsi'] == candidate['imsi'])
                if normalize_int32({k: v for k, v in saved.items() if k != '_id'}) != candidate:
                    raise Refused('Inserted document readback differs')
            if source() != candidates:
                raise Refused('Source static subscription changed during import')
            result.update(target_after=len(after), existing_unchanged=True, source_static_unchanged=True, passed=True)
        except Exception:
            result['error'] = 'Import or readback incomplete; inspect private backup and batch before any retry'
            result['passed'] = False
        finally:
            if attempted_start:
                try:
                    run([*compose, 'stop', '--timeout', '20', 'mongo'], timeout=45)
                    ids = run([*compose, 'ps', '-aq', 'mongo']).split()
                    for info in json.loads(run(['docker', 'inspect', *ids])) if ids else []:
                        if info['State']['Running'] or info['State']['ExitCode'] != 0 or info['State']['OOMKilled']:
                            raise Refused('Database did not stop cleanly')
                    run([*compose, 'rm', '-f', 'mongo'])
                    if NETWORK in run(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines():
                        network = json.loads(run(['docker', 'network', 'inspect', NETWORK]))[0]
                        if network.get('Containers') or network.get('Labels', {}).get('org.agentic-ocudu.owner') != PROJECT:
                            raise Refused('Network is in use; retained for inspection')
                        run(['docker', 'network', 'rm', NETWORK])
                    run(['docker', 'volume', 'inspect', VOLUME])
                    result['cleanup'] = True
                except Exception:
                    result['cleanup'] = False
                    result['passed'] = False
            private_json(directory / 'result.json', result)
        print(json.dumps(result), flush=True)
        return result['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-source', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-source-count', type=int, default=4)
    args = parser.parse_args()
    if args.check_source:
        records = source()
        print(json.dumps({'source_count': len(records), 'valid_static_material': True,
                          'target_queried': False, 'mutations': 0}))
        return len(records) == args.expected_source_count
    if os.geteuid() != 0:
        raise Refused('Run --apply from a terminal with sudo; no password is accepted by this tool')
    return apply(args.expected_source_count)


if __name__ == '__main__':
    try:
        raise SystemExit(0 if main() else 1)
    except Exception:
        print('Operation refused or incomplete. No sensitive diagnostics displayed; do not retry blindly.', file=sys.stderr)
        raise SystemExit(1)
