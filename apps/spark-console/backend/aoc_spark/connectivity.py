"""Bounded collector-only reachability evidence; never a Jetson end-to-end claim."""
import ipaddress
import json
import re
import subprocess
import time

from .domain import age_seconds, utc


TARGETS = {
    'ocudu': ('aoc-v2-open5gs-ext-dn-1', ipaddress.ip_network('10.0.0.0/24')),
}
GATEWAYS = {'ocudu': '172.28.81.14'}


class Reachability:
    def __init__(self, execute=subprocess.run, clock=time.monotonic):
        self.execute, self.clock, self.cache = execute, clock, {}

    def collect(self, devices, stack, epoch):
        candidates = []
        for device in devices:
            device['reachability'] = dict(state='unknown', reason='no_fresh_data_session',
                                          source='spark_ext_dn_icmp', observed_at=utc())
            if device['stack'] != stack or device.get('status') != 'ok' or device.get('registration') != 'registered':
                continue
            for session in device.get('sessions', []):
                try:
                    address = ipaddress.ip_address(session.get('address') or '')
                    network = TARGETS[stack][1]
                    eligible = (session['dnn'] == 'oai' and session['status'] == 'ok'
                                and -5 <= age_seconds(session['observed_at']) <= 90
                                and address in network and address not in (network.network_address, network.broadcast_address))
                    if eligible:
                        candidates.append((device, session, str(address)))
                except (ValueError, KeyError, TypeError):
                    continue
        counts = {}
        for _, _, address in candidates:
            counts[address] = counts.get(address, 0) + 1
        # At most four one-second probes per collection; cache requires two distinct samples.
        live_keys, budget = set(), 4
        for device, session, address in candidates:
            if counts[address] != 1:
                device['reachability']['reason'] = 'ambiguous_address_owner'
                continue
            key = (stack, epoch, device.get('epoch'), device['id'], session['id'], address)
            live_keys.add(key)
            old = self.cache.get(key)
            now = self.clock()
            if old and now - old['clock'] < 10:
                device['reachability'] = old['evidence'].copy()
                continue
            if not budget:
                device['reachability']['reason'] = 'probe_budget_pending'
                continue
            budget -= 1
            streak, state, reason = 0, 'unknown', 'probe_execution_failed'
            try:
                route = self.execute(['docker', 'exec', TARGETS[stack][0], 'ip', '-j', 'route', 'get', address],
                                     capture_output=True, text=True, timeout=2)
                paths = json.loads(route.stdout) if route.returncode == 0 else []
                if len(paths) != 1 or paths[0].get('gateway') != GATEWAYS[stack] or paths[0].get('dev') != 'eth0':
                    raise ValueError('probe_route_unverified')
                result = self.execute(['docker', 'exec', TARGETS[stack][0], 'ping', '-n', '-c', '1', '-W', '1', address],
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    streak = (old['streak'] if old and now - old['clock'] < 30 else 0) + 1
                    state, reason = ('reachable', 'spark_to_ue_address_only') if streak >= 2 else ('pending', 'probe_confirmation_pending')
                elif result.returncode == 1 and re.search(r'1 packets? transmitted', result.stdout or ''):
                    state, reason = 'unreachable', 'icmp_no_reply_not_session_release'
            except (OSError, subprocess.SubprocessError):
                pass
            except (ValueError, TypeError, KeyError):
                reason = 'probe_route_unverified'
            evidence = dict(state=state, reason=reason, source='spark_ext_dn_icmp', address=address, observed_at=utc())
            self.cache[key] = dict(clock=now, streak=streak, evidence=evidence)
            device['reachability'] = evidence.copy()
        self.cache = {k: v for k, v in self.cache.items() if k in live_keys}


def connection_state(device):
    """Registration and PDU reports cannot promote a device to connected."""
    current = device.get('status') == 'ok'
    sessions = device.get('sessions', [])
    fresh = [s for s in sessions if s.get('status') == 'ok']
    probe = device.get('reachability', {})
    try:
        recent_probe = current and -5 <= age_seconds(probe['observed_at']) <= 20
    except (KeyError, ValueError, TypeError):
        recent_probe = False
    if probe and not recent_probe:
        probe = {**probe, 'state': 'unknown', 'reason': 'probe_expired_or_unavailable'}
        device['reachability'] = probe
    layers = dict(registration=device.get('registration', 'unknown'),
                  radio='unverified', data_pdu='recent_report' if any(s['dnn'] == 'oai' for s in fresh) else 'unverified')
    state, reason = 'unknown', 'connection_evidence_incomplete'
    if current and device.get('registration') == 'deregistered':
        state, reason = 'disconnected', 'explicit_deregistration_report'
    elif current and device.get('source') == 'ocudu_scheduler':
        state = device.get('state', 'radio_observed')
        layers['radio'] = state
        reason = 'radio_context_not_subscriber_connection'
    elif current and device.get('registration') == 'registered':
        state, reason = 'registered', 'registration_not_data_connectivity'
    device.update(state=state, connection=dict(state=state, reason=reason, layers=layers),
                  session_counts=dict(recent=len(fresh), historical=len(sessions) - len(fresh)))
