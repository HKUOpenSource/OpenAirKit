"""Independent UPF counters; installation requires a root-owned opt-in marker."""
import json
import os
import subprocess
import time
from pathlib import Path
from .domain import observation, rate


def rules(stack):
    if stack != 'ocudu':
        raise ValueError('invalid_stack')
    gnb, upf = '172.28.81.1', '172.28.81.14'
    return f'''table inet aoc_spark {{
 counter n3_ul {{ }}
 counter n3_dl {{ }}
 counter n6_ul {{ }}
 counter n6_dl {{ }}
 chain input {{ type filter hook input priority -10; policy accept;
  ip saddr {gnb} ip daddr {upf} udp dport 2152 counter name n3_ul
 }}
 chain output {{ type filter hook output priority -10; policy accept;
  ip saddr {upf} ip daddr {gnb} udp dport 2152 counter name n3_dl
 }}
 chain forward {{ type filter hook forward priority -10; policy accept;
  iifname "ogstun" oifname "eth0" counter name n6_ul
  iifname "eth0" oifname "ogstun" counter name n6_dl
 }}
}}
'''


class Traffic:
    def __init__(self, run):
        self.run = run
        self.previous = {}
        self.prepared = set()

    def prepare(self, stack, pid):
        with (Path('/proc')/str(pid)/'ns/net').open('rb') as namespace:
            if os.fstat(namespace.fileno()).st_ino == Path('/proc/self/ns/net').stat().st_ino:
                raise ValueError('refusing_host_namespace_counters')
            # Pin the namespace so a container exit/PID reuse cannot redirect the mutation.
            prefix = ['nsenter', '--net=/proc/{}/fd/{}'.format(os.getpid(),namespace.fileno())]
            interfaces = json.loads(self.run(prefix + ['ip', '-j', 'link']))
            if not {'eth0', 'ogstun'} <= {v['ifname'] for v in interfaces}:
                raise ValueError('unexpected_upf_interfaces')
            exists = subprocess.run(prefix + ['nft', 'list', 'table', 'inet', 'aoc_spark'], capture_output=True, timeout=3)
            if exists.returncode:
                subprocess.run(prefix + ['nft', '--check', '-f', '-'], input=rules(stack), text=True, check=True, capture_output=True, timeout=3)
                subprocess.run(prefix + ['nft', '-f', '-'], input=rules(stack), text=True, check=True, capture_output=True, timeout=3)

    def collect(self, stack, container):
        state = container.get('State', {})
        pid, epoch = state.get('Pid'), state.get('StartedAt')
        if not pid or not state.get('Running'):
            return {}
        token = (stack, pid, epoch)
        if token not in self.prepared and os.geteuid() == 0 and Path('/etc/aoc-monitor/traffic-enabled').exists():
            try:
                self.prepare(stack, pid)
                self.prepared.add(token)
            except (OSError, ValueError, subprocess.SubprocessError):
                return {}
        try:
            raw = json.loads(self.run(['nsenter', '-t', str(pid), '-n', 'nft', '-j', 'list', 'table', 'inet', 'aoc_spark']))
            counts = {v['counter']['name']: int(v['counter']['bytes']) for v in raw['nftables'] if 'counter' in v and 'bytes' in v['counter']}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            return {}
        now, result = time.monotonic(), {}
        for boundary in ('n3', 'n6'):
            values = []
            for direction, label in (('ul','uplink_bps'), ('dl','downlink_bps')):
                key = (stack,boundary,direction)
                name = boundary + '_' + direction
                if name not in counts:
                    continue
                old = self.previous.get(key)
                elapsed = now - old[1] if old else None
                speed = rate(old[2], counts[name], elapsed) if old and old[0] == epoch else None
                self.previous[key] = (epoch,now,counts[name])
                values.append(observation('nft_counter',stack+':'+boundary,label,speed,'bit/s','ok' if speed is not None else 'unavailable',
                                          'ip_bytes_at_protocol_boundary' if speed is not None else 'warmup_or_counter_reset',elapsed))
            result[boundary] = values
        return result
