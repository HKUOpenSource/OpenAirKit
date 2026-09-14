"""Bounded, allowlisted adapters for the fixed Open5GS V2 infoAPI and metrics."""
import hashlib
import ipaddress
import json
import math
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .domain import observation, utc

ENDPOINTS = {
    'amf_ue': 'http://172.28.81.12:9090/ue-info?page=-1',
    'amf_gnb': 'http://172.28.81.12:9090/gnb-info?page=-1',
    'amf_metrics': 'http://172.28.81.12:9090/metrics',
    'smf_pdu': 'http://172.28.81.13:9090/pdu-info?page=-1',
    'smf_metrics': 'http://172.28.81.13:9090/metrics',
    'upf_metrics': 'http://172.28.81.14:9090/metrics',
}
MAX_RESPONSE = 1024 * 1024
DATA_POOL = ipaddress.ip_network('10.0.0.0/24')
METRICS = {
    'amf': {
        'gnb': 'gnbs', 'amf_session': 'sessions', 'ran_ue': 'ran_ues',
        'fivegs_amffunction_rm_registeredsubnbr': 'registered_subscribers',
    },
    'smf': {
        'pfcp_peers_active': 'pfcp_peers', 'ues_active': 'ues',
        'pfcp_sessions_active': 'pfcp_sessions', 'bearers_active': 'bearers',
    },
    'upf': {
        'pfcp_peers_active': 'pfcp_peers',
        'fivegs_upffunction_upf_sessionnbr': 'sessions',
        'fivegs_upffunction_upf_qosflows': 'qos_flows',
    },
}


def subscriber_id(supi):
    return 'ocudu:ue:' + hashlib.sha256(supi.encode()).hexdigest()[:20]


def valid_supi(value):
    return value if isinstance(value, str) and re.fullmatch(r'imsi-\d{14,16}', value) else None


def bounded_get(url, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={'Accept': 'application/json,text/plain'})
    with opener(request, timeout=2) as response:
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        raise ValueError('open5gs_response_too_large')
    return body.decode('utf-8')


def items(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise ValueError('invalid_open5gs_info_shape')
    pager = payload.get('pager', {})
    if not isinstance(pager, dict) or not isinstance(pager.get('count', len(payload['items'])), int):
        raise ValueError('invalid_open5gs_pager')
    return payload['items']


def parse_info(amf_payload, pdu_payload, gnb_payload, observed_at=None, epoch='open5gs-current'):
    at = observed_at or utc()
    amf, duplicate_amf = {}, set()
    for row in items(amf_payload):
        if not isinstance(row, dict) or not (supi := valid_supi(row.get('supi'))):
            continue
        if supi in amf:
            duplicate_amf.add(supi)
            continue
        gnb = row.get('gnb') if isinstance(row.get('gnb'), dict) else {}
        mm = row.get('mm_state')
        registration = 'registered' if mm == 'registered' else 'deregistered' if mm == 'deregistered' else 'unknown'
        identifiers = {key: gnb[key] for key in ('amf_ue_ngap_id', 'ran_ue_ngap_id', 'gnb_id', 'cell_id')
                       if isinstance(gnb.get(key), int)}
        amf[supi] = dict(id=subscriber_id(supi), stack='ocudu', epoch=epoch,
                          identity='Subscriber ****' + supi[-4:], identifiers=identifiers,
                          registration=registration, state=registration, status='ok', observed_at=at,
                          source='open5gs_info', correlation='amf_supi', metrics=[
                              {**observation('open5gs_info', subscriber_id(supi), 'cm_state', row.get('cm_state'), 'state',
                                             'ok' if row.get('cm_state') in ('connected', 'idle') else 'unavailable',
                                             'amf_current_mobility_state' if row.get('cm_state') in ('connected', 'idle') else 'amf_cm_state_missing'),
                               'observed_at': at}], sessions=[])
    for supi in duplicate_amf:
        amf.pop(supi, None)
    pdu_rows, duplicate_pdu = {}, set()
    for row in items(pdu_payload):
        if not isinstance(row, dict) or not (supi := valid_supi(row.get('supi'))):
            continue
        if supi in pdu_rows:
            duplicate_pdu.add(supi)
            continue
        pdu_rows[supi] = row
    for supi, row in pdu_rows.items():
        if supi in duplicate_pdu or supi in duplicate_amf:
            continue
        device = amf.get(supi)
        if device is None:
            device = dict(id=subscriber_id(supi), stack='ocudu', epoch=epoch,
                          identity='Subscriber ****' + supi[-4:], identifiers={}, registration='unknown',
                          state='unknown', status='ok', observed_at=at, source='open5gs_info',
                          correlation='smf_supi_only', metrics=[], sessions=[])
            amf[supi] = device
        else:
            device['correlation'] = 'amf_smf_supi'
        for pdu in row.get('pdu', []):
            if not isinstance(pdu, dict) or pdu.get('dnn') != 'oai' or not isinstance(pdu.get('psi'), int):
                continue
            address, pool_valid = None, False
            try:
                candidate = ipaddress.ip_address(pdu.get('ipv4', ''))
                if candidate.version == 4 and candidate in DATA_POOL and candidate not in (DATA_POOL.network_address, DATA_POOL.broadcast_address):
                    address, pool_valid = str(candidate), True
            except ValueError:
                pass
            qos = []
            for flow in pdu.get('qos_flows', []):
                if not isinstance(flow, dict):
                    continue
                qfi, five_qi = flow.get('qfi'), flow.get('5qi')
                if isinstance(qfi, int) and 0 <= qfi <= 63 and isinstance(five_qi, int) and 1 <= five_qi <= 255:
                    qos.append({'qfi': qfi, 'five_qi': five_qi})
            snssai = pdu.get('snssai') if isinstance(pdu.get('snssai'), dict) else {}
            state = pdu.get('pdu_state') if pdu.get('pdu_state') in ('active', 'inactive') else 'unknown'
            n3 = pdu.get('n3') if isinstance(pdu.get('n3'), dict) else {}
            gnb_n3 = n3.get('gnb') if isinstance(n3.get('gnb'), dict) else {}
            upf_n3 = n3.get('upf') if isinstance(n3.get('upf'), dict) else {}
            n3_verified = gnb_n3.get('addr') == '[172.28.81.1]:2152' and upf_n3.get('addr') == '[172.28.81.14]:2152'
            device['sessions'].append(dict(id=str(pdu['psi']), dnn='oai', address=address,
                pool_valid=pool_valid, sst=snssai.get('sst') if isinstance(snssai.get('sst'), int) else None,
                sd=snssai.get('sd') if isinstance(snssai.get('sd'), str) else None,
                five_qi=qos[0]['five_qi'] if len(qos) == 1 else None,
                qfi=qos[0]['qfi'] if len(qos) == 1 else None, qos_flows=qos, state=state,
                status='ok', source='open5gs_info', observed_at=at,
                ue_activity=row.get('ue_activity') if row.get('ue_activity') in ('active', 'idle') else 'unknown',
                n3_verified=n3_verified))
    owners = {}
    for device in amf.values():
        identifiers = device['identifiers']
        key = tuple(identifiers.get(name) for name in ('gnb_id', 'amf_ue_ngap_id', 'ran_ue_ngap_id'))
        if all(value is not None for value in key):
            owners.setdefault(key, []).append(device)
    for group in owners.values():
        if len(group) > 1:
            for device in group:
                device['identifiers'] = {}
                device['correlation'] = 'ambiguous_ngap_identifiers'
    observations = []
    active = [session for device in amf.values() for session in device['sessions']
              if session['state'] == 'active' and session['pool_valid']]
    five_qis = [flow['five_qi'] for session in active for flow in session['qos_flows']]
    observations.append({**observation('open5gs_info', 'ocudu:oai', 'active_pdu_count', len(active), 'count',
                                      reason='smf_current_active_sessions'), 'observed_at': at})
    observations.append({**observation('open5gs_info', 'ocudu:oai', 'observed_5qi', five_qis[0] if len(set(five_qis)) == 1 and five_qis else None,
                                      'index', 'ok' if five_qis else 'unavailable',
                                      'smf_current_qos_flow' if five_qis else 'no_current_qos_flow'), 'observed_at': at})
    observations.append({**observation('open5gs_info', 'ocudu:n3', 'active_session_paths',
                                      sum(1 for session in active if session['n3_verified']), 'count',
                                      reason='smf_pdu_info_endpoint_pair'), 'observed_at': at})
    gnbs = [row for row in items(gnb_payload) if isinstance(row, dict)]
    setup = [row for row in gnbs if isinstance(row.get('ng'), dict) and row['ng'].get('setup_success') is True]
    connected = sum(row.get('num_connected_ues', 0) for row in setup if isinstance(row.get('num_connected_ues'), int))
    observations.extend([
        {**observation('open5gs_info', 'ocudu', 'open5gs_gnb_count', len(gnbs), 'count'), 'observed_at': at},
        {**observation('open5gs_info', 'ocudu', 'ng_setup_success', len(setup) == 1, 'state'), 'observed_at': at},
        {**observation('open5gs_info', 'ocudu', 'amf_connected_ue_count', connected, 'count',
                       reason='amf_cm_connected_count'), 'observed_at': at},
    ])
    return list(amf.values()), observations, {'gnb_count': len(gnbs), 'setup_count': len(setup), 'connected_ues': connected}


def parse_prometheus(raw, role, observed_at=None):
    at = observed_at or utc(); totals = {}
    allowed = METRICS[role]
    for line in raw.splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^\r\n]*\})?\s+([^\s]+)', line)
        if not match or match[1] not in allowed:
            continue
        try:
            value = float(match[2])
        except ValueError:
            continue
        if not math.isfinite(value) or value < 0:
            continue
        totals[allowed[match[1]]] = totals.get(allowed[match[1]], 0) + value
    return [{**observation('open5gs_metrics', 'ocudu:' + role, name, value, 'count'), 'observed_at': at}
            for name, value in totals.items()]


class Open5GS:
    def __init__(self, getter=bounded_get):
        self.getter = getter

    def collect(self, epoch='open5gs-current'):
        at = utc(); observations = []; errors = {}
        names = ('amf_ue', 'smf_pdu', 'amf_gnb', 'amf_metrics', 'smf_metrics', 'upf_metrics')
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            futures = {name: pool.submit(self.getter, ENDPOINTS[name]) for name in names}
        raw = {}
        for name, future in futures.items():
            try:
                raw[name] = future.result()
            except (OSError, ValueError, TypeError):
                errors[name] = name + '_unavailable'
        documents = {}
        for name in ('amf_ue', 'smf_pdu', 'amf_gnb'):
            try:
                documents[name] = json.loads(raw[name])
            except (KeyError, ValueError, TypeError):
                errors[name] = name + '_unavailable'
        devices, details = [], {}
        if len(documents) == 3:
            try:
                devices, values, details = parse_info(documents['amf_ue'], documents['smf_pdu'], documents['amf_gnb'], at, epoch)
                observations.extend(values)
            except (ValueError, TypeError, KeyError):
                errors['info'] = 'open5gs_info_invalid'
        if not devices:
            for name, unit in (('active_pdu_count', 'count'), ('observed_5qi', 'index')):
                observations.append({**observation('open5gs_info', 'ocudu:oai', name, unit=unit,
                                                   status='unavailable', reason='open5gs_info_unavailable'), 'observed_at': at})
        for role in ('amf', 'smf', 'upf'):
            try:
                observations.extend(parse_prometheus(raw[role + '_metrics'], role, at))
            except (KeyError, ValueError, TypeError):
                observations.append({**observation('open5gs_metrics', 'ocudu:' + role, 'metrics_available',
                                                   status='unavailable', reason=role + '_metrics_unavailable'), 'observed_at': at})
        return dict(devices=devices, observations=observations, gnb=details, errors=errors)
