"""Run only in a disposable Linux container with --network none and NET_ADMIN.

The entry guard rejects a host namespace with any non-loopback interface.
Only modem discovery is substituted; routing, locking and journals are real.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys


def ip(*args):
    return subprocess.check_output(['ip', *args], text=True)


if (sys.platform != 'linux' or os.geteuid() != 0
        or os.environ.get('AOC_ISOLATED_ROUTE_TEST') != '1'
        or {row['ifname'] for row in json.loads(ip('-j', 'link', 'show'))} != {'lo'}):
    raise SystemExit('Requires an explicitly marked disposable network-none container')

from aoc_jetson import network
from aoc_jetson.config import DEVICE, DIAGNOSTICS, REFERENCE, SELECTION, RECOVERY, validate

for interface, address in [('wifi0', '192.0.2.2/24'), ('rndis0', '192.168.225.2/24'),
                            ('tailscale0', '198.18.0.1/32')]:
    ip('link', 'add', interface, 'type', 'dummy')
    ip('address', 'add', address, 'dev', interface)
    ip('link', 'set', interface, 'up')
ip('route', 'add', 'default', 'via', '192.0.2.1', 'dev', 'wifi0', 'metric', '30000')
ip('route', 'add', 'default', 'via', '192.168.225.1', 'dev', 'rndis0', 'metric', '100')
ip('route', 'add', '192.0.2.20/32', 'dev', 'tailscale0')
ip('route', 'add', '10.0.0.1/32', 'via', '192.168.225.1', 'dev', 'rndis0', 'proto', 'static')

config = validate({'schema_version': 3, 'name': 'agentic-ocudu-jetson-v2',
    'device': copy.deepcopy(DEVICE), 'network': copy.deepcopy(REFERENCE),
    'diagnostics': copy.deepcopy(DIAGNOSTICS), 'selection': copy.deepcopy(SELECTION),
    'recovery': copy.deepcopy(RECOVERY), 'state_dir': '/state', 'web_state_dir': '/state/web',
    'agent_socket': '/state/device.sock', 'commissioned': True, 'management_verified': True,
    'sim_sha256': '0' * 64, 'management': {'wifi_interface': 'wifi0',
        'tailscale_interface': 'tailscale0', 'spark_address': '192.0.2.20'}})
network.discover = lambda _config: {'data_interface': 'rndis0'}
defaults = ip('-j', '-4', 'route', 'show', 'default')
assert network.helper(config, 'prepare')['mutations'] == 2
assert network.helper(config, 'prepare')['mutations'] == 0
assert network.route_to('1.1.1.1')['dev'] == 'wifi0'
for _ in range(3):
    assert network.helper(config, 'promote')['ipv4_egress'] == 'rndis0'
    assert network.helper(config, 'promote')['mutations'] == 0
    assert network.helper(config, 'prepare')['mutations'] == 0
    assert network.route_to('1.1.1.1')['dev'] == 'rndis0'
    assert network.helper(config, 'fallback')['ipv4_egress'] == 'wifi0'
    assert network.helper(config, 'fallback')['mutations'] == 0
    assert network.route_to('8.8.8.8', '192.168.225.2')['dev'] == 'rndis0'
    assert network.route_to('192.0.2.20')['dev'] == 'tailscale0'
assert str(network.route_rows('172.28.81.15/32')[0]['protocol']) == '186'
assert network.route_to('172.28.81.15')['dev'] == 'rndis0'
network.helper(config, 'restore')
assert ip('-j', '-4', 'route', 'show', 'default') == defaults
assert not network.route_rows('172.28.81.15/32')
assert network.route_rows('10.0.0.1/32')  # Pre-existing route survives.

ip('route', 'add', '172.28.81.15/32', 'via', '192.0.2.1', 'dev', 'wifi0')
try:
    network.helper(config, 'prepare')
except ValueError as error:
    assert 'Conflicting' in str(error)
else:
    raise AssertionError('Conflicting route was not rejected')
assert not network.route_rows('8.8.8.8/32')
ip('route', 'del', '172.28.81.15/32')

network.helper(config, 'prepare')
ip('route', 'replace', '172.28.81.15/32', 'via', '192.168.225.254', 'dev', 'rndis0', 'proto', '186')
try:
    network.helper(config, 'restore')
except ValueError as error:
    assert 'owned route changed' in str(error)
else:
    raise AssertionError('Changed owned route was deleted')
assert network.route_rows('8.8.8.8/32')
ip('link', 'del', 'rndis0')
network.helper(config, 'fallback')
assert network.route_to('1.1.1.1')['dev'] == 'wifi0'
network.helper(config, 'restore')
network.helper(config, 'restore')
assert not Path('/state/network-state.json').exists()
assert not Path('/state/egress-state.json').exists()

# Re-enumeration restores dedicated probes and preference without touching NM.
ip('link', 'add', 'rndis1', 'type', 'dummy')
ip('address', 'add', '192.168.225.2/24', 'dev', 'rndis1')
ip('link', 'set', 'rndis1', 'up')
network.discover = lambda _config: {'data_interface': 'rndis1'}
network.helper(config, 'prepare')
network.helper(config, 'promote')
assert network.route_to('1.1.1.1')['dev'] == 'rndis1'
ip('link', 'del', 'rndis1')
ip('link', 'add', 'rndis2', 'type', 'dummy')
ip('address', 'add', '192.168.225.2/24', 'dev', 'rndis2')
ip('link', 'set', 'rndis2', 'up')
network.discover = lambda _config: {'data_interface': 'rndis2'}
network.helper(config, 'prepare')
network.helper(config, 'promote')
assert network.route_to('1.1.1.1')['dev'] == 'rndis2'
assert network.route_to('8.8.8.8')['dev'] == 'rndis2'
network.helper(config, 'restore')

# An administrator's high-priority default is rejected, never overwritten.
ip('route', 'add', 'default', 'via', '192.0.2.1', 'dev', 'wifi0', 'metric', '5')
try:
    network.helper(config, 'fallback')
except ValueError as error:
    assert 'conflicts' in str(error)
else:
    raise AssertionError('Foreign default was not rejected')
ip('route', 'del', 'default', 'via', '192.0.2.1', 'dev', 'wifi0', 'metric', '5')
assert len(json.loads(ip('-j', '-4', 'route', 'show', 'default'))) == 1
assert network.route_to('1.1.1.1')['dev'] == 'wifi0'
print(json.dumps({'passed': True, 'real_linux_routes': True, 'modem_discovery': 'substituted',
                  'cases': ['prepare', 'repeat', 'numeric_protocol', 'preserve_existing',
                            'reject_conflict', 'reject_changed_owner', 'cleanup_after_device_loss',
                            'three_failover_failback_cycles', 'bound_probes_during_fallback',
                            'usb_reenumeration', 'foreign_default_rejection']}))
