#!/usr/bin/env python3
"""Bounded, disposable empty-core test. No radio, subscribers or host route edits."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time


def run(argv, timeout=30, stdin=None):
    result = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(argv[:5]) + ': ' + result.stderr[-2000:])
    return result.stdout


def preflight(bundle, output, disposable=True):
    bundle = bundle.resolve()
    manifest = json.loads((bundle / 'bundle.json').read_text())
    project = manifest['project']
    if disposable and not re.fullmatch(r'aoc-v2-corecheck-[a-z0-9-]+', project):
        raise ValueError('Only disposable corecheck projects may use this tool')
    if not disposable and (project != 'aoc-v2-open5gs' or not manifest.get('database_auth')):
        raise ValueError('Provisioning requires the authenticated owned database')
    if manifest['scope'] != 'empty-core-no-rf' or manifest['production_ready'] is not False:
        raise ValueError('Not an empty-core validation bundle')
    if output.exists():
        raise ValueError('Evidence output already exists')
    for name, digest in manifest['files'].items():
        path = bundle / name
        if path.resolve().parent != bundle and bundle not in path.resolve().parents:
            raise ValueError('Bundle path escape')
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Bundle checksum mismatch: ' + name)
    expected = set(manifest['files']) | {'bundle.json'}
    if {str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file()} != expected:
        raise ValueError('Unexpected bundle files')
    for image in manifest['images'].values():
        info = json.loads(run(['docker', 'image', 'inspect', image]))[0]
        if info['Id'] != image or info['Architecture'] != 'arm64':
            raise ValueError('Image ID or architecture mismatch')
    if run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).strip():
        raise ValueError('Test project already exists')
    network = ipaddress.ip_network(manifest['subnet'])
    for route in json.loads(run(['ip', '-j', '-4', 'route', 'show', 'table', 'all'])):
        dest = route.get('dst', 'default')
        if dest != 'default' and network.overlaps(ipaddress.ip_network(dest, strict=False)):
            raise ValueError('Test subnet overlaps host route')
    ids = run(['docker', 'network', 'ls', '-q']).split()
    for item in json.loads(run(['docker', 'network', 'inspect', *ids])) if ids else []:
        for config in (item.get('IPAM') or {}).get('Config') or []:
            if config.get('Subnet') and ':' not in config['Subnet'] and network.overlaps(ipaddress.ip_network(config['Subnet'])):
                raise ValueError('Test subnet overlaps Docker IPAM')
    volume = project + '-mongo'
    if volume in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines():
        raise ValueError('Test volume already exists')
    compose = ['docker', 'compose', '--project-name', project, '--project-directory', str(bundle),
               '-f', str(bundle / 'compose.json')]
    run([*compose, 'config', '--quiet'])
    return manifest, compose, volume


def verify(bundle, output):
    bundle = bundle.resolve()
    manifest, compose, volume = preflight(bundle, output)
    project = manifest['project']
    output.mkdir(mode=0o700, parents=True)
    result = {'at': time.time(), 'project': project, 'scope': 'empty-core-no-rf',
              'passed': False, 'bundle_sha256': hashlib.sha256((bundle / 'bundle.json').read_bytes()).hexdigest(),
              'images': manifest['images'], 'cleanup': {}}
    containers = []
    try:
        run([*compose, 'up', '-d', '--wait', '--wait-timeout', '120'], timeout=150)
        containers = run([*compose, 'ps', '-aq']).split()
        states = json.loads(run(['docker', 'inspect', *containers]))
        result['health'] = {s['Config']['Labels']['com.docker.compose.service']:
                           s['State'].get('Health', {}).get('Status') for s in states}
        expected = set(json.loads((bundle / 'compose.json').read_text())['services'])
        if (set(result['health']) != expected or len(states) != len(expected)
                or any(v != 'healthy' for v in result['health'].values())):
            raise ValueError('Incomplete core health')
        result['associations'] = {}
        for nf in ('amf', 'smf', 'ausf', 'udm', 'udr', 'pcf', 'nssf', 'bsf'):
            logs = run([*compose, 'logs', '--no-color', nf])
            result['associations'][nf] = {'nrf_registered': 'NF registered' in logs}
        result['pfcp_associated'] = 'PFCP associated' in run([*compose, 'logs', '--no-color', 'smf'])
        if not all(v['nrf_registered'] for v in result['associations'].values()) or not result['pfcp_associated']:
            raise ValueError('NRF registration or PFCP association not confirmed')
        if manifest.get('n6'):
            result['n6_probe'] = {'scope': 'UPF-local-source-NAT-not-UE-or-GTP', 'connectivity': False}
            target = manifest['addresses']['ext-dn']
            run([*compose, 'exec', '-T', 'upf', 'ping', '-I', '10.0.0.1', '-c', '3', '-W', '2', target], timeout=15)
            code = ("import http.client; c=http.client.HTTPConnection('" + target + "',8080,timeout=3,"
                    "source_address=('10.0.0.1',0)); c.request('GET','/health'); r=c.getresponse(); "
                    "assert r.status==200 and r.read(128)==b'aoc-data-network-ok\\n'; c.close()")
            run([*compose, 'exec', '-T', 'upf', 'python3', '-c', code], timeout=10)
            result['n6_probe']['connectivity'] = True
            nat = json.loads(run([*compose, 'exec', '-T', 'upf', 'nft', '-j', 'list', 'table', 'ip', 'aoc_v2']))
            counters = [expr['counter']['packets'] for item in nat['nftables'] if 'rule' in item
                        for expr in item['rule']['expr'] if 'counter' in expr]
            result['n6_probe']['nat_packets'] = sum(counters)
            if not counters or sum(counters) == 0:
                raise ValueError('NAT rule did not observe traffic')
        mongo_args = [*compose, 'exec', '-T', 'mongo', 'mongosh', '--host', manifest['addresses']['mongo'], '--quiet', '--file', '/dev/stdin']
        auth = "const core=db.getSiblingDB('open5gs');"
        if manifest.get('database_auth'):
            auth += "const c=JSON.parse(require('fs').readFileSync('/run/secrets/subscriber-db.json','utf8'));if(!core.auth(c.username,c.password))quit(1);"
        run(mongo_args, stdin=auth + "core.validation_proof.insertOne({_id:'lifecycle',ok:true});")
        run([*compose, 'stop', '--timeout', '20'], timeout=60)
        stopped = json.loads(run(['docker', 'inspect', *containers]))
        result['shutdown'] = {s['Config']['Labels']['com.docker.compose.service']:
                              {'exit_code': s['State']['ExitCode'], 'oom': s['State']['OOMKilled']} for s in stopped}
        if any(s['exit_code'] != 0 or s['oom'] for s in result['shutdown'].values()):
            raise ValueError('Unclean stop')
        run([*compose, 'down', '--timeout', '20'], timeout=60)
        if volume not in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines():
            raise ValueError('Database volume lost on down')
        run([*compose, 'up', '-d', '--wait', '--wait-timeout', '120'], timeout=150)
        proof = run(mongo_args, stdin=auth + "printjson(core.validation_proof.findOne({_id:'lifecycle'}));")
        if 'lifecycle' not in proof or 'true' not in proof:
            raise ValueError('Database did not survive recreation')
        run(mongo_args, stdin=auth + "core.validation_proof.drop();")
        result['volume_survived_recreation'] = True
        result['passed'] = True
    except Exception as error:
        result['error'] = str(error)
        try:
            ids = run([*compose, 'ps', '-aq']).split()
            for item in json.loads(run(['docker', 'inspect', *ids])) if ids else []:
                nf = item['Config']['Labels']['com.docker.compose.service']
                (output / (nf + '-health.json')).write_text(json.dumps(item['State'], indent=2))
            (output / 'empty-core.log').write_text(run([*compose, 'logs', '--no-color', '--tail', '60']))
        except Exception as collection_error:
            result['evidence_error'] = str(collection_error)
    finally:
        try:
            run([*compose, 'stop', '--timeout', '20'], timeout=60)
            ids = run([*compose, 'ps', '-aq']).split()
            states = json.loads(run(['docker', 'inspect', *ids])) if ids else []
            result['cleanup']['exit_codes'] = {s['Config']['Labels']['com.docker.compose.service']: s['State']['ExitCode'] for s in states}
            if any(s['State']['ExitCode'] != 0 for s in states):
                result['passed'] = False
            run([*compose, 'down', '--timeout', '20'], timeout=60)
            labels = json.loads(run(['docker', 'volume', 'inspect', volume]))[0].get('Labels') or {}
            if labels.get('org.agentic-ocudu.owner') != project:
                raise ValueError('Test volume ownership mismatch')
            run(['docker', 'volume', 'rm', volume])
            result['cleanup']['containers_absent'] = not run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).strip()
            result['cleanup']['network_absent'] = project + '-core' not in run(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines()
            result['cleanup']['volume_absent'] = volume not in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
            if not all(result['cleanup'][key] for key in ('containers_absent', 'network_absent', 'volume_absent')):
                raise ValueError('Test resources remain')
        except Exception as error:
            result['cleanup']['error'] = str(error)
            result['passed'] = False
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.bundle, args.output) else 1)
