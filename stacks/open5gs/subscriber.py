"""Build one Open5GS data subscription from private static SIM material.

The returned document is secret. Never log it or pass it as a process argument.
"""
import json
import os
from pathlib import Path
import re
import stat
import hashlib
import subprocess


def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('SIM file must be regular, private and owned by the invoking user')
        if info.st_size > 4096:
            raise ValueError('SIM input is too large')
        return json.load(stream)


def document(material):
    fields = {'imsi': r'46003[0-9]{10}', 'ki': r'[a-fA-F0-9]{32}',
              'opc': r'[a-fA-F0-9]{32}', 'amf': r'[a-fA-F0-9]{4}'}
    if not isinstance(material, dict) or set(material) not in (set(fields), set(fields) | {'sqn'}):
        raise ValueError('Expected one SIM: imsi, ki, opc and amf; optional historical sqn is ignored')
    for name, pattern in fields.items():
        if not isinstance(material[name], str) or not re.fullmatch(pattern, material[name]):
            raise ValueError('Invalid static SIM field: ' + name)
    if 'sqn' in material and (not isinstance(material['sqn'], str) or not re.fullmatch(r'[a-fA-F0-9]{12}', material['sqn'])):
        raise ValueError('Invalid historical SQN format')
    ambr = {'uplink': {'value': 500, 'unit': 2}, 'downlink': {'value': 1000, 'unit': 2}}
    return {'schema_version': 1, 'imsi': material['imsi'], 'msisdn': [], 'imeisv': [],
            'mme_host': [], 'mme_realm': [], 'purge_flag': [],
            'security': {'k': material['ki'].lower(), 'op': None, 'opc': material['opc'].lower(),
                         'amf': material['amf'].lower(), 'sqn': {'$numberLong': '0'}},
            'slice': [{'sst': 1, 'default_indicator': True, 'session': [
                {'name': 'oai', 'type': 1, 'ambr': ambr, 'pcc_rule': [],
                 'qos': {'index': 9, 'arp': {'priority_level': 8,
                     'pre_emption_capability': 1, 'pre_emption_vulnerability': 2}}}]}],
            'ambr': ambr, 'access_restriction_data': 32, 'network_access_mode': 0,
            'subscriber_status': 0, 'operator_determined_barring': 0,
            'subscribed_rau_tau_timer': 12, '__v': 0}


def insert_script(doc):
    # EJSON preserves SQN as BSON int64, which the pinned Open5GS DBI requires.
    # This script is sent only via stdin to mongosh --file /dev/stdin.
    payload = json.dumps(json.dumps(doc, separators=(',', ':')))
    return '''try {
const fs = require('fs');
const credentials = JSON.parse(fs.readFileSync('/run/secrets/subscriber-db.json', 'utf8'));
const core = db.getSiblingDB('open5gs');
if (!core.auth(credentials.username, credentials.password)) throw new Error('auth');
const candidate = EJSON.parse(''' + payload + ''', {relaxed: false});
core.subscribers.createIndex({imsi: 1}, {unique: true});
if (core.subscribers.countDocuments({imsi: candidate.imsi}) !== 0) {
  print(JSON.stringify({inserted: false, reason: 'already_exists', sqn_changed: false}));
  quit(2);
}
core.subscribers.insertOne(candidate);
const saved = core.subscribers.findOne({imsi: candidate.imsi});
const session = saved.slice[0].session[0];
if (saved.slice.length !== 1 || saved.slice[0].sst !== 1 || saved.slice[0].session.length !== 1 ||
    session.name !== 'oai' || session.type !== 1 || session.qos.index !== 9 ||
    saved.security.sqn._bsontype !== 'Long' ||
    saved.security.sqn.toString() !== '0') throw new Error('readback');
print(JSON.stringify({inserted: true, dnn: 'oai', ipv4: true, sst: 1, five_qi: 9,
  sqn_policy: 'independent-zero-initialization', resynchronization_verified: false}));
} catch (_) {
  print(JSON.stringify({inserted: null, reason: 'import_or_readback_failed', automatic_retry: false}));
  quit(1);
}
'''


def insert(bundle, material_path, identity_path):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / 'bundle.json').read_text())
    if manifest.get('project') != 'aoc-v2-open5gs' or not manifest.get('database_auth'):
        raise ValueError('Real subscription requires the independent authenticated deployment')
    for name, digest in manifest['files'].items():
        path = bundle / name
        if bundle not in path.resolve().parents or path.is_symlink():
            raise ValueError('Invalid deployment path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Deployment checksum mismatch')
    material = read_private(material_path)
    expected = read_private(identity_path)
    if set(expected) != {'imsi'} or material.get('imsi') != expected['imsi']:
        raise ValueError('Private identity confirmation does not match SIM input')
    doc = document(material)
    ids = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=aoc-v2-open5gs',
                                   '--filter', 'label=com.docker.compose.service=mongo'], text=True, timeout=10).split()
    if len(ids) != 1:
        raise ValueError('Expected exactly one owned running MongoDB')
    info = json.loads(subprocess.check_output(['docker', 'inspect', ids[0]], text=True, timeout=10))[0]
    if info['Image'] != manifest['images']['mongodb'] or info['Config']['Labels'].get('org.agentic-ocudu.owner') != manifest['project']:
        raise ValueError('Database image or ownership mismatch')
    proc = subprocess.run(['docker', 'exec', '-i', ids[0], 'mongosh', '--host', manifest['addresses']['mongo'],
                           '--quiet', '--file', '/dev/stdin'], input=insert_script(doc), text=True,
                          capture_output=True, timeout=30)
    if proc.returncode == 2:
        raise ValueError('Subscriber already exists; nothing overwritten, SQN preserved')
    if proc.returncode:
        raise ValueError('Import/readback failed; credentials withheld. Do not automatically retry')
    result = json.loads(proc.stdout.strip())
    if result.get('inserted') is not True:
        raise ValueError('Unexpected import acknowledgement')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--material', type=Path, required=True)
    parser.add_argument('--identity', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(insert(args.bundle, args.material, args.identity)))
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit('Subscription import refused or incomplete; no sensitive diagnostic exported')
