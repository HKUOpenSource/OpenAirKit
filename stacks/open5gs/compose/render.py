#!/usr/bin/env python3
"""Render a pinned, empty 5GC bundle. Does not start services or import subscribers."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import shutil
import secrets

ROOT = Path(__file__).resolve().parents[1]
ADDRESSES = dict(mongo=10, nrf=11, amf=12, smf=13, upf=14,
                 **{'ext-dn': 15}, udr=16, udm=17, ausf=18, pcf=20, nssf=21, bsf=22)


def configurations(subnet):
    network = ipaddress.ip_network(subnet)
    if network.version != 4 or network.prefixlen != 24:
        raise ValueError('Core subnet must be an IPv4 /24')
    if network.overlaps(ipaddress.ip_network('10.0.0.0/24')):
        raise ValueError('Core network overlaps UE pool')
    addr = {name: str(network[offset]) for name, offset in ADDRESSES.items()}
    plmn = {'mcc': '460', 'mnc': '03'}
    session = [{'subnet': '10.0.0.0/24', 'gateway': '10.0.0.1', 'dnn': 'oai', 'dev': 'ogstun'}]
    result = {}
    for nf in ADDRESSES.keys() - {'mongo', 'ext-dn'}:
        body = {'sbi': {'server': [{'address': addr[nf], 'port': 7777}]}}
        if nf != 'nrf':
            body['sbi']['client'] = {'nrf': [{'uri': 'http://' + addr['nrf'] + ':7777'}]}
        doc = {'logger': {'level': 'info'}, 'global': {'max': {'ue': 32}}, nf: body}
        if nf in ('udr', 'pcf'):
            doc['db_uri'] = 'mongodb://' + addr['mongo'] + ':27017/open5gs'
        result[nf] = doc
    result['nrf']['nrf']['serving'] = [{'plmn_id': plmn}]
    result['amf']['amf'].update({
        'ngap': {'server': [{'address': addr['amf']}]},
        'metrics': {'server': [{'address': addr['amf'], 'port': 9090}]},
        'guami': [{'plmn_id': plmn, 'amf_id': {'region': 2, 'set': 1}}],
        'tai': [{'plmn_id': plmn, 'tac': 1}],
        'plmn_support': [{'plmn_id': plmn, 's_nssai': [{'sst': 1}]}],
        'security': {'integrity_order': ['NIA2', 'NIA1'], 'ciphering_order': ['NEA0']},
        'network_name': {'full': 'Agentic-OCUDU'}, 'amf_name': 'aoc-v2-amf',
        'time': {'t3512': {'value': 540}}})
    result['smf']['smf'].update({
        'pfcp': {'server': [{'address': addr['smf']}], 'client': {'upf': [{'address': addr['upf']}]}},
        'gtpc': {'server': [{'address': addr['smf']}]},
        'gtpu': {'server': [{'address': addr['smf']}]},
        'metrics': {'server': [{'address': addr['smf'], 'port': 9090}]},
        'session': session, 'dns': ['1.1.1.1'], 'mtu': 1400,
        'info': [{'s_nssai': [{'sst': 1, 'dnn': ['oai']}]}]})
    result['upf']['upf'] = {
        'pfcp': {'server': [{'address': addr['upf']}]},
        'gtpu': {'server': [{'address': addr['upf']}]},
        'metrics': {'server': [{'address': addr['upf'], 'port': 9090}]}, 'session': session}
    result['nssf']['nssf']['sbi']['client']['nsi'] = [
        {'uri': 'http://' + addr['nrf'] + ':7777', 's_nssai': {'sst': 1}}]
    return addr, result


def render(output, subnet='172.28.81.0/24', project='aoc-v2-open5gs', database_auth=False, n6=False):
    import re
    if not re.fullmatch(r'aoc-v2-[a-z0-9-]{1,30}', project):
        raise ValueError('Invalid owned project name')
    lock = json.loads((ROOT / 'artifacts.lock.json').read_text())
    sources = ROOT / 'sources.lock.json'
    if hashlib.sha256(sources.read_bytes()).hexdigest() != lock['source_lock_sha256']:
        raise ValueError('Source lock differs from verified artifacts')
    images = {key: lock[key]['image_id'] for key in ('open5gs', 'mongodb')}
    images['connectivity'] = lock['connectivity_runtime']['image_id']
    if n6:
        images['n6'] = lock['network_runtime']['image_id']
    if any(not re.fullmatch(r'sha256:[a-f0-9]{64}', value) for value in images.values()):
        raise ValueError('Unpinned image')
    addr, configs = configurations(subnet)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / 'config').mkdir()
    shutil.copyfile(Path(__file__).with_name('runtime.py'), output / 'runtime.py')
    if database_auth:
        credentials = {'username': 'aoc_core', 'password': secrets.token_hex(24)}
        (output / 'secrets').mkdir(mode=0o700)
        (output / 'secrets/root-user').write_text('aoc_admin\n')
        (output / 'secrets/root-password').write_text(secrets.token_hex(24) + '\n')
        (output / 'secrets/subscriber-db.json').write_text(json.dumps(credentials))
        # Individual file mounts must be readable by MongoDB's non-root entrypoint.
        # The enclosing 0700 bundle and secrets directories protect them on the host.
        for secret in (output / 'secrets').iterdir():
            secret.chmod(0o644)
        (output / 'init-db.js').write_text("const c=JSON.parse(require('fs').readFileSync('/run/secrets/subscriber-db.json','utf8'));\n"
            "db.getSiblingDB('open5gs').createUser({user:c.username,pwd:c.password,roles:[{role:'readWrite',db:'open5gs'}]});\n")
        (output / 'mongo-health.js').write_text("try { const c=JSON.parse(require('fs').readFileSync('/run/secrets/subscriber-db.json','utf8'));\n"
            "const d=db.getSiblingDB('open5gs'); if(!d.auth(c.username,c.password)) quit(1);\n"
            "quit(d.runCommand({ping:1}).ok===1?0:1); } catch (_) { quit(1); }\n")
        # MongoDB drops privileges before reading these individual file mounts.
        for name in ('init-db.js', 'mongo-health.js'):
            (output / name).chmod(0o644)
        for nf in ('udr', 'pcf'):
            configs[nf]['db_uri'] = 'mongodb://' + credentials['username'] + ':' + credentials['password'] + '@' + addr['mongo'] + ':27017/open5gs'
    for nf, doc in configs.items():
        (output / 'config' / (nf + '.json')).write_text(json.dumps(doc, indent=2) + '\n')
        # File-mounted configs must be readable with all NF capabilities dropped.
        # The owner-only bundle directory protects credentials on the host.
        (output / 'config' / (nf + '.json')).chmod(0o644)
    services = {}
    for nf in ADDRESSES:
        service = {'image': images['mongodb' if nf == 'mongo' else 'connectivity' if nf == 'ext-dn' else 'open5gs'],
                   'pull_policy': 'never', 'platform': 'linux/arm64', 'restart': 'no',
                   'stop_grace_period': '20s', 'networks': {'core': {'ipv4_address': addr[nf]}},
                   'security_opt': ['no-new-privileges:true'], 'cap_drop': ['ALL'],
                   'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}},
                   'labels': {'org.agentic-ocudu.owner': project}}
        health = {'interval': '3s', 'timeout': '3s', 'retries': 20, 'start_period': '5s'}
        if nf == 'mongo':
            service.update({'user': 'mongodb', 'entrypoint': ['mongod'],
                            'command': ['--bind_ip', addr[nf], '--port', '27017'],
                            # Avoid TCMalloc per-CPU rseq startup failures on newer Linux kernels (SERVER-125742).
                            'environment': {'GLIBC_TUNABLES': 'glibc.pthread.rseq=1'},
                            'volumes': ['mongo-data:/data/db']})
            health['test'] = ['CMD', 'mongosh', '--host', addr[nf], '--quiet', '--eval',
                              'quit(db.adminCommand({ping:1}).ok === 1 ? 0 : 1)']
            if database_auth:
                service.pop('user')
                service.pop('entrypoint')
                service['command'] = ['mongod', '--auth', '--bind_ip', addr[nf] + ',127.0.0.1']
                service['cap_add'] = ['CHOWN', 'SETUID', 'SETGID', 'DAC_OVERRIDE']
                service['environment'] = {'MONGO_INITDB_ROOT_USERNAME_FILE': '/run/secrets/root-user',
                    'MONGO_INITDB_ROOT_PASSWORD_FILE': '/run/secrets/root-password', 'MONGO_INITDB_DATABASE': 'open5gs',
                    'GLIBC_TUNABLES': 'glibc.pthread.rseq=1'}
                service['volumes'] += ['./secrets/' + name + ':/run/secrets/' + name + ':ro'
                                       for name in ('root-user', 'root-password', 'subscriber-db.json')]
                service['volumes'] += ['./init-db.js:/docker-entrypoint-initdb.d/aoc.js:ro',
                                       './mongo-health.js:/opt/aoc/mongo-health.js:ro']
                health['test'] = ['CMD', 'mongosh', '--host', addr[nf], '--quiet', '--file', '/opt/aoc/mongo-health.js']
        else:
            service['volumes'] = ['./runtime.py:/opt/aoc/runtime.py:ro']
            service['entrypoint'] = ['python3', '/opt/aoc/runtime.py']
            service['command'] = ['run', nf, addr[nf]]
            health['test'] = ['CMD', 'python3', '/opt/aoc/runtime.py', 'health', nf, addr[nf]]
            dependencies = []
            if nf in configs:
                service['volumes'].append('./config/' + nf + '.json:/etc/aoc/nf.json:ro')
                if nf not in ('nrf', 'upf'):
                    dependencies.append('nrf')
                if nf in ('udr', 'pcf'):
                    dependencies.append('mongo')
                if nf == 'smf':
                    dependencies.extend(('upf', 'pcf'))
                if nf == 'pcf':
                    dependencies.append('bsf')
            if nf == 'upf':
                service['cap_add'] = ['NET_ADMIN']
                service['devices'] = ['/dev/net/tun:/dev/net/tun']
                service['sysctls'] = {'net.ipv4.ip_forward': '1'}
                if n6:
                    service['image'] = images['n6']
                    service['environment'] = {'AOC_N6_ENABLED': '1'}
                    service['cap_add'].append('NET_RAW')
            if dependencies:
                service['depends_on'] = {d: {'condition': 'service_healthy'} for d in dependencies}
        service['healthcheck'] = health
        services[nf] = service
    compose = {'name': project, 'services': services,
                   'networks': {'core': {'name': project + '-core', 'internal': not n6,
                   'labels': {'org.agentic-ocudu.owner': project},
                   'ipam': {'config': [{'subnet': subnet}]}}},
               'volumes': {'mongo-data': {'name': project + '-mongo',
                   'labels': {'org.agentic-ocudu.owner': project}}}}
    (output / 'compose.json').write_text(json.dumps(compose, indent=2) + '\n')
    manifest = {'scope': 'empty-core-no-rf', 'production_ready': False,
                'project': project, 'subnet': subnet, 'images': images, 'addresses': addr, 'database_auth': database_auth, 'n6': n6,
                'files': {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--subnet', default='172.28.81.0/24')
    parser.add_argument('--project', default='aoc-v2-open5gs')
    parser.add_argument('--database-auth', action='store_true')
    parser.add_argument('--n6', action='store_true')
    args = parser.parse_args()
    result = render(args.output, args.subnet, args.project, args.database_auth, args.n6)
    print(json.dumps({key: result[key] for key in ('scope', 'production_ready', 'project', 'database_auth', 'images')}))
