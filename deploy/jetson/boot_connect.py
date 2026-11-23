#!/usr/bin/python3
"""Opt-in boot coordinator for an already commissioned, pinned Jetson release.

Installed separately from the immutable application release. Site configuration
and journals are root-owned; no SIM authentication material is accepted here.
"""
from pathlib import Path
import argparse
import csv
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time

BASE = Path('/opt/agentic-ocudu/jetson/current')
SITE = Path('/etc/aoc-v2-jetson/boot.json')
STATE = Path('/var/lib/aoc-v2-jetson-boot')
DEVICE = Path('/etc/aoc-v2-jetson/device.json')
READS = frozenset({'AT', 'ATI', 'AT+CPIN?', 'AT+CIMI', 'AT+CFUN?',
                  'AT+COPS?', 'AT+C5GREG?', 'AT+CEREG?', 'AT+QENG="servingcell"',
                  'AT+CGDCONT?', 'AT+QMAPWAC?', 'AT+QMAP="MPDN_rule"',
                  'AT+QCFG="usbnet"', 'AT+QCFG="usbspeed"',
                  'AT+QNWPREFCFG="nr5g_band"', 'AT+QNWPREFCFG="nr5g_disable_mode"',
                  'AT+QNWPREFCFG="mode_pref"'})
CONFIG = ('AT+CGDCONT?', 'AT+QMAPWAC?', 'AT+QMAP="MPDN_rule"',
          'AT+QCFG="usbnet"', 'AT+QCFG="usbspeed"',
          'AT+QNWPREFCFG="nr5g_band"', 'AT+QNWPREFCFG="nr5g_disable_mode"')


def run(argv, timeout=15, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Host command failed: ' + Path(argv[0]).name)
    return result


def atomic(path, value, mode=0o600):
    temporary = path.with_name('.' + path.name + '.' + str(time.time_ns()))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
    os.fchmod(fd, mode)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def trusted_json(path):
    if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
        raise ValueError('Untrusted root configuration')
    return json.loads(path.read_text())


def runtime():
    site = trusted_json(SITE)
    if hashlib.sha256(DEVICE.read_bytes()).hexdigest() != site['device_sha256']:
        raise ValueError('Commissioned device configuration changed')
    raw = (BASE / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != site['manifest_sha256']:
        raise ValueError('Pinned application release changed')
    manifest = json.loads(raw)
    entry = BASE / 'deploy/manage.py'
    if hashlib.sha256(entry.read_bytes()).hexdigest() != manifest['files']['deploy/manage.py']:
        raise ValueError('Installed release verifier changed')
    spec = importlib.util.spec_from_file_location('boot_installed_verifier', entry)
    manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manager)
    manager.verify_installed(BASE.resolve(strict=True), manifest)
    sys.path[:0] = [str(BASE / 'backend'), str(BASE / 'venv/lib/python3.10/site-packages')]
    from aoc_jetson.config import load
    config = load(str(DEVICE))
    if not config['commissioned'] or config.get('simulation') or config['sim_sha256'] != site['sim_sha256']:
        raise ValueError('Commissioned identity differs')
    return site, config


def rpc(request):
    if request.get('op') not in {'status', 'maintenance', 'create', 'run', 'job'}:
        raise ValueError('Unsupported platform request')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(55)
        client.connect('/run/aoc-v2-jetson/device.sock')
        client.sendall(json.dumps(request).encode() + b'\n')
        with client.makefile('rb') as stream:
            value = json.loads(stream.readline(1024 * 1024))
    if value.get('ok') is not True:
        raise RuntimeError('Platform request rejected')
    return value['result']


GATEWAY_CACHE_SECONDS = 15.0
_GATEWAY_OK = {}


def probe_gateway(wifi, gateway):
    """Probe the management gateway, retrying with paced pings to tolerate ICMP rate-limiting."""
    if not run(['ping', '-n', '-I', wifi, '-c', '1', '-W', '2', gateway], check=False).returncode:
        return True
    return not run(['ping', '-n', '-I', wifi, '-c', '3', '-i', '1', '-W', '2', gateway], timeout=15, check=False).returncode


def management(config):
    from aoc_jetson.network import inspect_management
    state = inspect_management(config)
    wifi = state['wifi_interface']
    if not run(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', wifi]).stdout.startswith('100'):
        _GATEWAY_OK.clear()
        raise ValueError('Management Wi-Fi disconnected')
    key = (wifi, state['wifi_gateway'])
    last_ok = _GATEWAY_OK.get(key)
    if last_ok is None or time.monotonic() - last_ok >= GATEWAY_CACHE_SECONDS:
        if not probe_gateway(wifi, state['wifi_gateway']):
            _GATEWAY_OK.pop(key, None)
            raise ValueError('Management gateway unreachable')
        _GATEWAY_OK[key] = time.monotonic()
    return state


def wait_ready(config, seconds=300):
    from aoc_jetson.network import inspect
    from aoc_jetson.hardware import discover
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            _GATEWAY_OK.clear()
            management(config)
            found = discover(config)
            inspect(config, require_management=True)
            return found
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            time.sleep(3)
    raise TimeoutError('Boot hardware, DHCP or management readiness deadline')


def terminal(lines):
    return bool(lines) and (lines[-1] in ('OK', 'ERROR') or lines[-1].startswith(('+CME ERROR:', '+CMS ERROR:')))


class Serial:
    def __init__(self, config):
        self.config = config
        self.known = True

    def __enter__(self):
        import serial
        from aoc_jetson.hardware import discover
        port = discover(self.config)['at_port']
        if run(['fuser', port], check=False).returncode != 1:
            raise ValueError('AT interface is owned by another process')
        self.port = serial.Serial(port, 115200, timeout=.2, write_timeout=3, exclusive=True)
        fcntl.ioctl(self.port.fileno(), 0x540C)
        return self

    def __exit__(self, *unused):
        self.port.close()

    def exchange(self, command, timeout=15):
        selection = 'AT+COPS=1,2,"' + self.config['network']['plmn'] + '",12'
        if command not in READS and command != selection:
            raise ValueError('Outside fixed boot command surface')
        if not self.known:
            raise RuntimeError('Previous AT completion unknown; no further sends')
        self.known = False
        self.port.reset_input_buffer()
        packet = (command + '\r').encode()
        if self.port.write(packet) != len(packet):
            raise OSError('Partial AT command')
        deadline, pending, lines = time.monotonic() + timeout, b'', []
        while time.monotonic() < deadline:
            pending += self.port.read(4096)
            if len(pending) > 32768:
                raise ValueError('Oversized response')
            while b'\n' in pending:
                raw, pending = pending.split(b'\n', 1)
                line = raw.decode(errors='replace').strip()
                if line and line != command:
                    lines.append(line)
                    if terminal(lines):
                        self.known = True
                        return lines
        raise TimeoutError('AT completion unknown')

    def query(self, command):
        if command not in READS:
            raise ValueError('Outside fixed read surface')
        return self.exchange(command)

    def verify(self):
        ready, identity = self.query('AT+CPIN?'), self.query('AT+CIMI')
        ids = [x for x in identity if re.fullmatch(r'\d{14,16}', x)]
        if (ready != ['+CPIN: READY', 'OK'] or identity[-1:] != ['OK'] or len(ids) != 1
                or hashlib.sha256(ids[0].encode()).hexdigest() != self.config['sim_sha256']):
            raise ValueError('Commissioned SIM not ready or different')

    def wait_sim(self, seconds=60):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.query('AT+CPIN?') == ['+CPIN: READY', 'OK']:
                self.verify()
                return
            time.sleep(3)
        raise TimeoutError('SIM readiness deadline')

    def select_once(self, report, save):
        if 'selection' in report:
            raise ValueError('Selection intent already exists; do not replay')
        self.verify()
        _GATEWAY_OK.clear()
        management(self.config)
        plmn = self.config['network']['plmn']
        if not re.fullmatch(r'\d{5,6}', plmn):
            raise ValueError('Invalid commissioned PLMN')
        report['selection'] = {'terminal': False}
        save()
        lines = self.exchange('AT+COPS=1,2,"' + plmn + '",12', timeout=190)
        report['selection'].update(terminal=True, accepted=lines[-1:] == ['OK'], response=lines)
        save()


def canonical(command, lines):
    if lines[-1:] != ['OK']:
        raise ValueError('Configuration readback rejected')
    prefix = '+CGDCONT:' if command == 'AT+CGDCONT?' else ('+QMAPWAC:' if command == 'AT+QMAPWAC?' else
             '+QMAP:' if command.startswith('AT+QMAP=') else '+QNWPREFCFG:' if command.startswith('AT+QNWPREFCFG=') else '+QCFG:')
    rows = [next(csv.reader([x.split(':', 1)[1].strip()], skipinitialspace=True)) for x in lines if x.startswith(prefix)]
    if command == 'AT+CGDCONT?':
        if any(len(r) < 4 for r in rows) or len({r[0] for r in rows}) != len(rows):
            raise ValueError('Malformed or ambiguous contexts')
        # Preserve configured profiles; vendor runtime CIDs and assigned IPs are not settings.
        rows = [r[:3] + r[4:] for r in rows if 1 <= int(r[0]) <= 16]
    if not rows:
        raise ValueError('Missing configuration readback')
    return sorted([list(r) for r in rows])


def configuration(modem):
    return {q: canonical(q, modem.query(q)) for q in CONFIG}


def check_preserved(expected, actual):
    if expected != actual:
        raise ValueError('Protected modem configuration changed')


def target(modem):
    from aoc_jetson.modem import registration, serving_cell
    reg = registration(modem.query('AT+C5GREG?'), modem.query('AT+CEREG?'))
    cell = serving_cell(modem.query('AT+QENG="servingcell"'))
    modem.observation = {'registration': reg, 'radio': cell}
    policy = modem.config['selection']
    return (reg['registered_5gs'] and cell.get('plmn') == modem.config['network']['plmn']
            and cell.get('rat') == policy['rat']
            and all(policy[k] is None or cell.get(k) == policy[k] for k in ('band', 'pci', 'ssb_arfcn')))


def wait_target(modem, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        management(modem.config)
        if target(modem):
            return True
        time.sleep(4)
    return False


def proof(value, now):
    net = value.get('network', {})
    if (value.get('quality') != 'ok' or not all(value.get(k) for k in
            ('connected', 'registered', 'lab_policy_match', 'management_protected'))
            or not 0 <= now - value.get('evidence_at', 0) <= 20
            or not net.get('data_interface') or not net.get('data_address')):
        return None
    stamps = []
    for key in ('gateway', 'upf', 'ext_dn', 'public'):
        p = value.get('probes', {}).get(key, {})
        if (p.get('state') != 'ok' or p.get('quality', 'ok') != 'ok'
                or not 0 <= now - p.get('at', 0) <= 20 or p.get('interface') != net['data_interface']
                or p.get('source') != net['data_address']):
            return None
        stamps.append(p['at'])
    return tuple(stamps)


def wait_data(config, report, save, clock=time.monotonic, wall=time.time, sleep=time.sleep):
    deadline, steady, previous, sets = clock() + 150, None, None, 0
    while True:
        if steady is None and clock() >= deadline:
            raise TimeoutError('Fresh bound cellular data deadline')
        management(config)
        value = rpc({'op': 'status'})
        current = proof(value, wall())
        good = current is not None and value.get('routing', {}).get('mode') == 'cellular'
        if steady is not None and not good:
            raise ValueError('Cellular proof lost during boot acceptance')
        if good and (previous is None or all(a > b for a, b in zip(current, previous))):
            sets += 1
            previous = current
        elif not good:
            sets, previous = 0, None
        if sets >= 2 and steady is None:
            steady = clock()
        report.update(fresh_probe_sets=sets, healthy_seconds=round(clock() - steady, 1) if steady is not None else 0,
                      cellular_default=good, management_verified=bool(value.get('management_protected')),
                      automatic_recovery_active=value.get('recovery_paused') is False)
        save()
        if steady is not None and clock() - steady >= 120:
            if value.get('maintenance') or value.get('active_job') or value.get('recovery_paused') is not False:
                raise ValueError('Platform control not idle with recovery enabled')
            return
        sleep(4)


def current_boot_id():
    value = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise ValueError('Invalid host boot identity')
    return value


def connect(site, config):
    boot_id = current_boot_id()
    private = STATE / 'private'
    lock = os.open(private / 'connect.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ledger = private / ('boot-' + boot_id + '.json')
    if ledger.exists():
        raise ValueError('This boot already has an operation record; no replay')
    pending = private / 'uncertain-selection.json'
    if pending.exists():
        raise ValueError('Earlier selection completion unknown; operator inspection required')
    report = {'schema': 1, 'boot_id': boot_id, 'status': 'running', 'stage': 'readiness',
              'maintenance_retained': False, 'sim_writes': 0, 'usb_writes': 0}

    def save():
        report['time_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        report.setdefault('timeline', {}).setdefault(report['stage'],
            {'epoch': time.time(), 'uptime_seconds': round(time.monotonic(), 1)})
        atomic(ledger, report)
        keys = ('schema', 'boot_id', 'status', 'stage', 'time_utc', 'maintenance_retained',
                'selection', 'error_type', 'error', 'job_state', 'fresh_probe_sets', 'healthy_seconds',
                'cellular_default', 'management_verified', 'automatic_recovery_active', 'usb_speed_mbps',
                'timeline', 'configuration_differences', 'observed_network_mode')
        atomic(STATE / 'public/status.json', {k: report[k] for k in keys if k in report}, 0o644)

    maintenance, modem = False, None
    try:
        save()
        wait_ready(config, 90)
        value = rpc({'op': 'status'})
        if value.get('active_job') or value.get('maintenance'):
            raise ValueError('Boot requires idle platform, not an earlier maintenance incident')
        _GATEWAY_OK.clear()
        management(config)
        maintenance = True
        rpc({'op': 'maintenance', 'enabled': True})
        report['stage'] = 'identity_and_registration'
        save()
        with Serial(config) as modem:
            modem.wait_sim()
            report['pre_configuration'] = configuration(modem)
            report['configuration_differences'] = [q for q in CONFIG if site['modem_configuration'].get(q) != report['pre_configuration'].get(q)]
            save()
            check_preserved(site['modem_configuration'], report['pre_configuration'])
            report['usb_speed_mbps'] = usb_speed(config)
            if report['usb_speed_mbps'] != site['usb_speed_mbps']:
                raise ValueError('Actual USB negotiation differs from approved baseline')
            natural = wait_target(modem, 90)
            report['registration_observation'] = getattr(modem, 'observation', {})
            save()
            if not natural:
                atomic(pending, {'boot_id': boot_id, 'intent': True})
                modem.select_once(report, save)
                pending.unlink()
                registered = wait_target(modem, 75)
                report['registration_observation'] = getattr(modem, 'observation', {})
                save()
                if not registered:
                    raise ValueError('Target lab registration not confirmed')
            report['post_configuration'] = configuration(modem)
            report['configuration_differences'] = [q for q in CONFIG if site['modem_configuration'].get(q) != report['post_configuration'].get(q)]
            save()
            check_preserved(site['modem_configuration'], report['post_configuration'])
            mode = canonical('AT+QNWPREFCFG="mode_pref"', modem.query('AT+QNWPREFCFG="mode_pref"'))
            report['observed_network_mode'] = mode
            save()
            if len(mode) != 1 or mode[0][1].upper() not in ('AUTO', 'NR5G', 'LTE:NR5G', 'NR5G:LTE'):
                raise ValueError('Unsupported observed network mode')
        rpc({'op': 'maintenance', 'enabled': False})
        maintenance = False
        report['stage'] = 'standard_setup'
        save()
        job = rpc({'op': 'create', 'kind': 'setup', 'revision': config['revision'], 'params': {'mode': 'automatic'}})
        report['job_id'] = job['id']
        save()
        rpc({'op': 'run', 'id': job['id'], 'confirmed': True})
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            management(config)
            job = rpc({'op': 'job', 'id': job['id']})
            report['job_state'] = job['state']
            save()
            if job['state'] == 'complete':
                break
            if job['state'] in {'failed', 'cancelled', 'interrupted'}:
                raise ValueError('Standard boot setup did not complete')
            time.sleep(3)
        else:
            raise TimeoutError('Standard boot setup deadline; no task replay')
        report['stage'] = 'bound_data_acceptance'
        save()
        wait_data(config, report, save)
        report.update(status='completed', stage='complete')
    except BaseException as error:
        report.update(status='stopped', error_type=type(error).__name__,
                      error=re.sub(r'\d{14,22}', '[REDACTED]', str(error))[:200])
        # Never send another AT command after an unknown response.
        if maintenance and (modem is None or modem.known):
            try:
                rpc({'op': 'maintenance', 'enabled': False})
                maintenance = False
            except Exception:
                pass
    finally:
        report['maintenance_retained'] = maintenance
        save()
    return 0 if report['status'] == 'completed' else 1


def usb_speed(config):
    from aoc_jetson.hardware import discover, usb_parent
    found = discover(config)
    return (usb_parent(Path('/sys/class/tty') / Path(found['at_port']).name / 'device') / 'speed').read_text().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('ready', 'connect'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Administrator execution required')
    os.umask(0o077)
    site, config = runtime()
    if args.action == 'ready':
        wait_ready(config)
        return 0
    return connect(site, config)


if __name__ == '__main__':
    raise SystemExit(main())
