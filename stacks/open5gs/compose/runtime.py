#!/usr/bin/env python3
"""Container-only entrypoints and exact process/socket readiness checks."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

N6_RULES = '''add table ip aoc_v2
add chain ip aoc_v2 postrouting { type nat hook postrouting priority srcnat; policy accept; }
add rule ip aoc_v2 postrouting ip saddr 10.0.0.0/24 oifname "eth0" counter masquerade
add chain ip aoc_v2 forward { type filter hook forward priority mangle; policy accept; }
add rule ip aoc_v2 forward ip saddr 10.0.0.0/24 tcp flags syn tcp option maxseg size 1401-65535 counter tcp option maxseg size set 1400
add rule ip aoc_v2 forward ip daddr 10.0.0.0/24 tcp flags syn tcp option maxseg size 1401-65535 counter tcp option maxseg size set 1400
'''
import urllib.request


def health(nf, address):
    if nf == 'ext-dn':
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with http.open('http://' + address + ':8080/health', timeout=2) as response:
            if response.status != 200 or response.read(128) != b'aoc-data-network-ok\n':
                raise RuntimeError('Data network endpoint not ready')
        return
    exe = 'open5gs-' + nf + 'd'
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
             'amf': [('tcp', 7777), ('sctp', 38412)]}.get(nf, [('tcp', 7777)])
    for proto, port in ports:
        output = subprocess.check_output(['ss', '-H', '-ln', '-' + {'tcp': 't', 'udp': 'u', 'sctp': 'S'}[proto]], text=True)
        if not any(address + ':' + str(port) in line.split() for line in output.splitlines()):
            raise RuntimeError('Expected socket is not bound')
    if nf == 'upf' and os.environ.get('AOC_N6_ENABLED') == '1':
        rules = json.loads(subprocess.check_output(['nft', '-j', 'list', 'table', 'ip', 'aoc_v2'], text=True))
        if not any('rule' in item for item in rules['nftables']):
            raise RuntimeError('N6 NAT rule missing')


class ConnectivityHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'aoc-data-network-ok\n' if self.path == '/health' else b'not found\n'
        self.send_response(200 if self.path == '/health' else 404)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def setup(self):
        self.request.settimeout(2)
        super().setup()

    def log_message(self, _format, *_args):
        pass


def connectivity_server(address):
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with HTTPServer((address, 8080), ConnectivityHandler) as server:
        server.timeout = .5
        while not stopping:
            server.handle_request()


def run(nf, address):
    if nf == 'ext-dn':
        return connectivity_server(address)
    if nf == 'upf':
        subprocess.run(['ip', 'tuntap', 'add', 'dev', 'ogstun', 'mode', 'tun'], check=True)
        subprocess.run(['ip', 'addr', 'add', '10.0.0.1/24', 'dev', 'ogstun'], check=True)
        subprocess.run(['ip', 'link', 'set', 'dev', 'ogstun', 'mtu', '1440', 'up'], check=True)
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
