#!/usr/bin/env python3
"""Independent V2 stack lifecycle; fixed installed paths and owned resources only."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

BASE = Path('/opt/agentic-ocudu/v2')
CORE = BASE / 'core'
STATE = Path('/var/lib/agentic-ocudu/v2')
LOG = Path('/var/log/agentic-ocudu/v2/gnb.log')
PROJECT = 'aoc-v2-open5gs'
UNITS = ('aoc-v2-radio.service', 'aoc-v2-core.service')
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']


def run(argv, timeout=30):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root'})
    if result.returncode:
        # Config and NF output can contain authentication material; keep it private.
        raise RuntimeError('Command failed (exit %d): %s' % (result.returncode, ' '.join(argv[:3])))
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_tree(root, files):
    if root.is_symlink() or not root.is_dir() or not files:
        raise ValueError('Release must be a nonempty real directory')
    root = root.resolve()
    for name, expected in files.items():
        relative = Path(name)
        path = root / relative
        if (relative.is_absolute() or '..' in relative.parts
                or any(part.is_symlink() for part in (path, *path.parents) if part != root)
                or not path.is_file() or root not in path.resolve().parents
                or digest(path) != expected):
            raise ValueError('Release integrity failed: ' + name)


def secure_tree(root):
    for path in (root, *root.parents, *root.rglob('*')):
        info = path.lstat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Release ownership or permissions invalid')


def manifest():
    secure_tree(BASE)
    release = json.loads((BASE / 'release.json').read_text())
    verify_tree(BASE, release['files'])
    spec = json.loads((CORE / 'bundle.json').read_text())
    verify_tree(CORE, spec['files'])
    if (spec['project'] != PROJECT or not spec['database_auth'] or not spec['n6']
            or spec['subnet'] != '172.28.81.0/24'):
        raise ValueError('Authenticated V2 N6 bundle required')
    actual = {str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()}
    if actual != set(release['files']) | {'release.json'}:
        raise ValueError('Unlisted release files')
    return spec


def compose(*args, timeout=60):
    return run([*DOCKER, 'compose', '-p', PROJECT, '--project-directory', str(CORE),
                '-f', str(CORE / 'compose.json'), *args], timeout)


def containers():
    ids = run([*DOCKER, 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT]).split()
    return json.loads(run([*DOCKER, 'inspect', *ids])) if ids else []


def owned(items, spec):
    for item in items:
        labels = item['Config'].get('Labels') or {}
        if (labels.get('com.docker.compose.project') != PROJECT
                or labels.get('org.agentic-ocudu.owner') != PROJECT
                or labels.get('com.docker.compose.service') not in spec['addresses']
                or item['Image'] not in spec['images'].values()):
            raise ValueError('Unexpected container under owned project label')


def core_ready(spec):
    states = containers()
    owned(states, spec)
    expected = set(compose('config', '--services').splitlines())
    if not expected or not expected.issubset(spec['addresses']):
        raise ValueError('Compose service set is empty or outside the bundle manifest')
    actual = [s['Config']['Labels']['com.docker.compose.service'] for s in states]
    missing, extra = expected - set(actual), set(actual) - expected
    duplicates = {name for name in actual if actual.count(name) > 1}
    unhealthy = {s['Config']['Labels']['com.docker.compose.service']:
                 {'running': s['State']['Running'],
                  'health': s['State'].get('Health', {}).get('Status', 'missing')}
                 for s in states if not s['State']['Running'] or
                 s['State'].get('Health', {}).get('Status') != 'healthy'}
    if missing or extra or duplicates or unhealthy:
        raise ValueError('Core readiness failed: ' + json.dumps({
            'expected_count': len(expected), 'missing': sorted(missing),
            'extra': sorted(extra), 'duplicates': sorted(duplicates), 'unhealthy': unhealthy}))


def resources(spec):
    for image in spec['images'].values():
        item = json.loads(run([*DOCKER, 'image', 'inspect', image]))[0]
        if item['Id'] != image or item['Architecture'] != 'arm64':
            raise ValueError('Pinned ARM64 image missing')
    volume = json.loads(run([*DOCKER, 'volume', 'inspect', PROJECT + '-mongo']))[0]
    if (volume.get('Labels') or {}).get('org.agentic-ocudu.owner') != PROJECT:
        raise ValueError('Provisioned database volume ownership mismatch')
    owned(containers(), spec)
    subnet = ipaddress.ip_network(spec['subnet'])
    ids = run([*DOCKER, 'network', 'ls', '-q']).split()
    bridges = set()
    for net in json.loads(run([*DOCKER, 'network', 'inspect', *ids])) if ids else []:
        own = net['Name'] == PROJECT + '-core' and (net.get('Labels') or {}).get('org.agentic-ocudu.owner') == PROJECT
        if own:
            bridges.add((net.get('Options') or {}).get('com.docker.network.bridge.name', 'br-' + net['Id'][:12]))
        for entry in (net.get('IPAM') or {}).get('Config') or []:
            if entry.get('Subnet') and ':' not in entry['Subnet'] and subnet.overlaps(ipaddress.ip_network(entry['Subnet'])) and not own:
                raise ValueError('Core subnet conflicts with another Docker network')
    for route in json.loads(run(['ip', '-j', '-4', 'route', 'show', 'table', 'all'])):
        dst = route.get('dst', 'default')
        if dst != 'default' and route.get('dev') not in bridges:
            network = ipaddress.ip_network(dst, strict=False)
            if subnet.overlaps(network) or ipaddress.ip_network('10.0.0.0/24').overlaps(network):
                raise ValueError('Core or UE pool conflicts with a foreign host route')
    compose('config', '--quiet')


def usb_free():
    found = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if (path / 'idVendor').read_text().strip() == '2500' and (path / 'idProduct').read_text().strip() == '0020':
                found.append(path)
        except OSError:
            continue
    if len(found) != 1:
        raise ValueError('Expected exactly one B210')
    dev = found[0]
    if float((dev / 'speed').read_text()) < 5000:
        raise ValueError('B210 requires a SuperSpeed USB connection')
    node = '/dev/bus/usb/%03d/%03d' % (int((dev / 'busnum').read_text()), int((dev / 'devnum').read_text()))
    check = subprocess.run(['fuser', node], capture_output=True, text=True, timeout=10)
    if check.returncode != 1 or check.stdout.strip() or check.stderr.strip():
        raise ValueError('B210 is occupied or ownership inspection failed; stop its owner first')
    return node


def radio_config(serial):
    if not re.fullmatch('[A-Za-z0-9]{1,32}', serial):
        raise ValueError('Invalid UHD serial')
    return {
        'cu_cp': {'amf': {'addrs': '172.28.81.12', 'port': 38412, 'bind_addrs': '172.28.81.1',
            'supported_tracking_areas': [{'tac': 1, 'plmn_list': [{'plmn': '46003', 'tai_slice_support_list': [{'sst': 1}]}]}]}},
        'cu_up': {'ngu': {'socket': [{'bind_addr': '172.28.81.1'}]}},
        'ru_sdr': {'device_driver': 'uhd', 'device_args': 'type=b200,serial=' + serial + ',num_recv_frames=256,num_send_frames=256',
            'srate': 46.08, 'otw_format': 'sc16', 'clock': 'internal', 'sync': 'internal', 'tx_gain': 80, 'rx_gain': 54},
        'cell_cfg': {'dl_arfcn': 643392, 'band': 78, 'channel_bandwidth_MHz': 40, 'common_scs': 30,
            'plmn': '46003', 'tac': 1, 'pci': 666, 'nof_antennas_dl': 1, 'nof_antennas_ul': 1,
            'pdsch': {'mcs_table': 'qam256'},
            'pusch': {'mcs_table': 'qam256', 'max_ue_mcs': 27},
            'tdd_ul_dl_cfg': {'dl_ul_tx_period': 10, 'nof_dl_slots': 6, 'nof_dl_symbols': 6, 'nof_ul_slots': 3, 'nof_ul_symbols': 4}},
        'remote_control': {'enabled': False},
        'log': {'filename': str(LOG), 'all_level': 'warning', 'cu_level': 'info',
                'ngap_level': 'info'},
        'pcap': {'mac_enable': False, 'ngap_enable': False}}


def record(phase, **fields):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    value = {'at': time.time(), 'phase': phase, **fields}
    temporary = STATE / 'lifecycle.tmp'
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(STATE / 'lifecycle.json')
    print(json.dumps(value), flush=True)


def prepare(spec):
    resources(spec)
    core_ready(spec)
    usb_free()
    raw = run([str(BASE / 'bin/probe-b210')], 45)
    rows = [json.loads(x.split('=', 1)[1]) for x in raw.splitlines() if x.startswith('AOC_PROBE_JSON=')]
    if len(rows) != 1:
        raise ValueError('UHD probe returned no unique device')
    probe = rows[0]
    for direction, gain in (('tx', 80), ('rx', 54)):
        if not probe[direction + '_min'] <= gain <= probe[direction + '_max']:
            raise ValueError('Reviewed gain outside device range')
    previous = STATE / 'b210.json'
    if previous.exists() and json.loads(previous.read_text())['serial'] != probe['serial']:
        raise ValueError('B210 identity changed')
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    previous.write_text(json.dumps(probe))
    (STATE / 'gnb.json').write_text(json.dumps(radio_config(probe['serial']), indent=2))
    run([str(BASE / 'bin/gnb'), '--dryrun', '-c', str(STATE / 'gnb.json')], 30)
    LOG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if LOG.exists():
        LOG.rename(LOG.with_name('gnb-%d.log' % time.time_ns()))
    record('radio-prepared', configuration_reviewed=True, rf_accepted=False)


def show(unit):
    return dict(line.split('=', 1) for line in run(['systemctl', 'show', unit, '-p', 'ActiveState',
        '-p', 'SubState', '-p', 'MainPID', '-p', 'Result', '-p', 'ExecMainStatus']).splitlines() if '=' in line)


def association(raw, pid):
    return any('ESTAB' in line and 'pid=%d,' % pid in line and '172.28.81.12:38412' in line.split()
        and any(re.fullmatch(r'172\.28\.81\.1(?:%[\w.-]+)?:\d+', x) for x in line.split()) for line in raw.splitlines())


def n2_ready(spec):
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = 'http://' + spec['addresses']['amf'] + ':9090/gnb-info?page=-1'
    try:
        with http.open(endpoint, timeout=3) as response:
            rows = json.loads(response.read(1024 * 1024)).get('items', [])
        return len(rows) == 1 and rows[0].get('ng', {}).get('setup_success') is True
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def radio_health(spec, timeout=160):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = show(UNITS[0])
        pid = int(status.get('MainPID', '0'))
        if status.get('ActiveState') in ('inactive', 'failed'):
            raise ValueError('Radio exited before N2 readiness')
        if (pid and Path('/proc/%d/exe' % pid).resolve() == BASE / 'bin/gnb'
                and association(run(['ss', '-H', '-n', '-p', '-A', 'sctp']), pid)
                and n2_ready(spec)):
            core_ready(spec)
            record('n2-ready', ue_accepted=False)
            return
        time.sleep(1)
    raise TimeoutError('Current N2 association and NG Setup not confirmed')


def core_stop(spec):
    owned(containers(), spec)
    compose('stop', '--timeout', '20', timeout=90)
    states = containers()
    failures = {s['Config']['Labels']['com.docker.compose.service']: s['State']['ExitCode']
                for s in states if s['State']['Running'] or s['State']['ExitCode'] != 0 or s['State']['OOMKilled']}
    if failures:
        record('unclean-core-stop', failures=failures)
        raise ValueError('Unclean container exit; resources retained for diagnosis')
    compose('down', '--timeout', '20', timeout=90)
    if containers() or PROJECT + '-core' in run([*DOCKER, 'network', 'ls', '--format', '{{.Name}}']).splitlines():
        raise ValueError('Owned network or containers remain')


@contextmanager
def lock():
    with open('/run/lock/aoc-v2-stack.lock', 'a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stop(spec):
    run(['systemctl', 'stop', UNITS[0]], 60)
    if show(UNITS[0]).get('ActiveState') not in ('inactive', 'failed'):
        raise ValueError('Radio did not stop; core retained')
    if show(UNITS[0]).get('Result') not in ('success', ''):
        raise ValueError('Radio failure retained; inspect before stopping core')
    run(['systemctl', 'stop', UNITS[1]], 240)
    if show(UNITS[1]).get('ActiveState') not in ('inactive', 'failed') or containers():
        raise ValueError('Core resources remain; inspection required')
    if show(UNITS[1]).get('Result') not in ('success', ''):
        raise ValueError('Core failure retained; inspection required')
    record('stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'prepare', 'start', 'stop', 'status',
                                         'core-start', 'core-stop', 'radio-health'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run the installed controller with administrator privileges')
    spec = manifest()
    if args.action == 'status':
        print(json.dumps({'services': {u: show(u) for u in UNITS}, 'containers': [
            {'service': s['Config']['Labels']['com.docker.compose.service'], 'state': s['State']['Status'],
             'health': s['State'].get('Health', {}).get('Status')} for s in containers()]}))
        return
    # Unit callbacks cannot reacquire the outer CLI lock while systemctl waits.
    if args.action == 'core-start':
        resources(spec)
        compose('up', '-d', '--wait', '--wait-timeout', '120', timeout=160)
        core_ready(spec)
        return
    if args.action == 'core-stop':
        core_stop(spec)
        return
    if args.action == 'radio-health':
        radio_health(spec)
        return
    if args.action == 'prepare':
        prepare(spec)
        return
    with lock():
        if args.action == 'preflight':
            resources(spec)
            usb_free()
            record('preflight-passed', rf_accepted=False)
        elif args.action == 'stop':
            stop(spec)
        else:
            resources(spec)
            if show(UNITS[0]).get('ActiveState') == 'active':
                radio_health(spec, 5)
                return
            usb_free()
            record('starting')
            try:
                run(['systemctl', 'start', UNITS[0]], 360)
                radio_health(spec, 5)
            except Exception:
                record('start-failed', inspection_required=True)
                raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('AOC V2 ERROR: ' + str(error), flush=True)
        raise SystemExit(1)
