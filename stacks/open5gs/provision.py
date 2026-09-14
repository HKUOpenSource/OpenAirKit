#!/usr/bin/env python3
"""One-time authenticated provisioning. Start only new MongoDB and retain it stopped."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from compose.verify_bundle import preflight, run
from subscriber import insert


def provision(bundle, material, identity, output):
    manifest, compose, volume = preflight(bundle, output, disposable=False)
    output.mkdir(mode=0o700, parents=True)
    result = {'at': time.time(), 'scope': 'single-sim-new-mongodb-only', 'passed': False,
              'resynchronization_verified': False, 'cleanup': {},
              'bundle_sha256': hashlib.sha256((bundle / 'bundle.json').read_bytes()).hexdigest()}
    try:
        run([*compose, 'up', '-d', '--wait', '--wait-timeout', '90', 'mongo'], timeout=120)
        result['subscription'] = insert(bundle, material, identity)
        result['passed'] = True
    except Exception:
        # Database/driver exceptions can include secrets. Keep details off the console and Git.
        result['error'] = 'Provisioning failed or acknowledgement incomplete; preserve database, no automatic retry'
    finally:
        try:
            run([*compose, 'stop', '--timeout', '20'], timeout=45)
            ids = run([*compose, 'ps', '-aq']).split()
            states = json.loads(run(['docker', 'inspect', *ids])) if ids else []
            result['cleanup']['exit_codes'] = [s['State']['ExitCode'] for s in states]
            if len(states) != 1 or states[0]['State']['ExitCode'] != 0 or states[0]['State']['OOMKilled']:
                raise RuntimeError('Database shutdown not verified')
            run([*compose, 'down', '--timeout', '20'], timeout=45)
            result['cleanup']['volume_retained'] = volume in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
            result['cleanup']['network_absent'] = manifest['project'] + '-core' not in run(['docker', 'network', 'ls', '--format', '{{.Name}}']).splitlines()
            if not all(result['cleanup'][k] for k in ('volume_retained', 'network_absent')):
                raise RuntimeError('Database or network state not verified')
        except Exception:
            result['passed'] = False
            result['cleanup']['error'] = 'Cleanup incomplete; inspect only the owned project before proceeding'
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'material', 'identity', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if provision(args.bundle.resolve(), args.material, args.identity, args.output) else 1)
