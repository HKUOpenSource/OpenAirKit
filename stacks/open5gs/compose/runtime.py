#!/usr/bin/env python3
"""Container-only entrypoints and exact process/socket readiness checks."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

N6_RULES = '''add table ip aoc_v2
add chain ip aoc_v2 postrouting { type nat hook postrouting priority srcnat; policy accept; }
add rule ip aoc_v2 postrouting ip saddr 10.0.0.0/24 oifname "eth0" counter masquerade
'''
import urllib.request


def health(nf, address):
    exe = 'iperf3' if nf == 'ext-dn' else 'open5gs-' + nf + 'd'
    found = False
    for path in Path('/proc').glob('[0-9]*/exe'):
        try:
            if path.resolve().name == exe:
                found = True
                break
        except OSError:
            pass
    if not found:
        raise RuntimeError('Expected daemon is not running')
    if nf in ('amf', 'smf', 'upf'):
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with http.open('http://' + address + ':9090/metrics', timeout=2) as response:
            if b'# HELP' not in response.read():
                raise RuntimeError('Metrics not ready')
    ports = {'upf': [('udp', 8805), ('udp', 2152)],
             'smf': [('tcp', 7777), ('udp', 8805)],
             'amf': [('tcp', 7777), ('sctp', 38412)],
             'ext-dn': [('tcp', 5201)]}.get(nf, [('tcp', 7777)])
    for proto, port in ports:
        output = subprocess.check_output(['ss', '-H', '-ln', '-' + {'tcp': 't', 'udp': 'u', 'sctp': 'S'}[proto]], text=True)
        if not any(address + ':' + str(port) in line.split() for line in output.splitlines()):
            raise RuntimeError('Expected socket is not bound')
    if nf == 'upf' and os.environ.get('AOC_N6_ENABLED') == '1':
        rules = json.loads(subprocess.check_output(['nft', '-j', 'list', 'table', 'ip', 'aoc_v2'], text=True))
        if not any('rule' in item for item in rules['nftables']):
            raise RuntimeError('N6 NAT rule missing')


def iperf_exit_code(code, stop_requested, forced):
    # iperf3 returns 1 on SIGINT; record it, normalize only an orderly requested stop.
    return 0 if stop_requested and not forced and code in (0, 1) else (code or 1)


def iperf_server(address):
    state = {'stopping': False}
    child = subprocess.Popen(['iperf3', '-s', '-B', address, '-p', '5201'], start_new_session=True)

    def stop(_signum, _frame):
        if child.poll() is None and not state['stopping']:
            state['stopping'] = True
            child.send_signal(signal.SIGINT)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while child.poll() is None and not state['stopping']:
        time.sleep(0.1)
    forced = False
    try:
        code = child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        forced = True
        child.kill()
        code = child.wait(timeout=3)
    print(json.dumps({'iperf_exit_code': code, 'stop_requested': state['stopping'], 'forced': forced}), flush=True)
    raise SystemExit(iperf_exit_code(code, state['stopping'], forced))


def run(nf, address):
    if nf == 'ext-dn':
        iperf_server(address)
    if nf == 'upf':
        subprocess.run(['ip', 'tuntap', 'add', 'dev', 'ogstun', 'mode', 'tun'], check=True)
        subprocess.run(['ip', 'addr', 'add', '10.0.0.1/24', 'dev', 'ogstun'], check=True)
        subprocess.run(['ip', 'link', 'set', 'ogstun', 'up'], check=True)
        if os.environ.get('AOC_N6_ENABLED') == '1':
            subprocess.run(['nft', '-f', '-'], input=N6_RULES, text=True, check=True)
    binary = '/opt/open5gs/bin/open5gs-' + nf + 'd'
    os.execv(binary, [binary, '-c', '/etc/aoc/nf.json'])


if __name__ == '__main__':
    mode, nf, address = sys.argv[1:]
    socket.inet_aton(address)
    if nf not in ('nrf', 'amf', 'smf', 'upf', 'udr', 'udm', 'ausf', 'pcf', 'nssf', 'bsf', 'ext-dn'):
        raise SystemExit('Unsupported NF')
    if mode == 'health':
        health(nf, address)
    elif mode == 'run':
        run(nf, address)
    else:
        raise SystemExit('Unsupported operation')
