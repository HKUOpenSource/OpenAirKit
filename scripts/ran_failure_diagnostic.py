"""Export bounded, redacted OCUDU failure evidence without changing the stack."""
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


START = '2026-09-08T09:31:00'
END = '2026-09-08T09:36:00'
COMPONENT = re.compile(r'\[(NGAP|RRC|CU-CP|CU-CP-F1|CU-UP|DU-MNG|DU-F1|RLC|PDCP)\s*\]')
SIGNAL = re.compile(r'fail|reject|unsuccess|timeout|timed out|cause|not support|not found|'
                    r'PDU.*[Ss]ession|PDUSession|[Cc]ontext|[Rr]econfig|[Ss]ecurity', re.I)


def clean(text):
    text = re.sub(r'\d{14,}', '[identity]', text)
    return re.sub(r'\b[0-9a-fA-F]{32,}\b', '[redacted]', text)[:1200]


def scan(path, max_bytes=256 * 1024 * 1024):
    target, recent = deque(maxlen=240), deque(maxlen=100)
    counters = Counter()
    first = last = None
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        offset = max(0, size - max_bytes)
        handle.seek(offset)
        if offset:
            handle.readline()
        # Limit reads even if the live file grows while it is being inspected.
        while handle.tell() < size:
            raw = handle.readline(min(65536, size - handle.tell()))
            if not raw:
                break
            line = raw.decode('utf-8', errors='replace').strip()
            if not re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', line):
                continue
            stamp = line[:19]
            first = first or stamp
            last = stamp
            for key in ('Real-time failure in RF: underflow', 'Real-time failure in RF: late',
                        'Maximum number of reTxs', 'RLC max ReTxs'):
                if key in line:
                    counters[key] += 1
            if COMPONENT.search(line) and SIGNAL.search(line):
                recent.append(clean(line))
                if START <= stamp <= END:
                    target.append(clean(line))
    return dict(file_bytes=size, scan_offset=offset, max_scan_bytes=max_bytes,
                first_timestamp=first, last_timestamp=last,
                requested_window=[START, END],
                covers_window=bool(first and first <= START and last >= END),
                counts_in_scanned_range=dict(counters),
                window_events=list(target), recent_events=list(recent))


def config_summary(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    fields = {
        'log': ('all_level', 'phy_level', 'mac_level', 'rlc_level', 'pdcp_level',
                'rrc_level', 'ngap_level', 'f1ap_level', 'e1ap_level'),
        'ru_sdr': ('srate', 'otw_format', 'clock', 'sync', 'tx_gain', 'rx_gain'),
        'cell_cfg': ('dl_arfcn', 'band', 'channel_bandwidth_MHz', 'common_scs', 'pci',
                     'nof_antennas_dl', 'nof_antennas_ul'),
    }
    result = {section: {key: value.get(section, {})[key] for key in keys
                        if key in value.get(section, {})} for section, keys in fields.items()}
    result['sha256'] = hashlib.sha256(raw).hexdigest()
    return result


def collect():
    result = {'read_only': True, 'collected_at': datetime.now(timezone.utc).isoformat()}
    for key, action in (
        ('ran_log', lambda: scan(Path('/var/log/agentic-ocudu/gnb.log'))),
        ('config', lambda: config_summary(Path('/etc/agentic-ocudu/ocudu/gnb.json'))),
    ):
        try:
            result[key] = action()
        except (OSError, ValueError) as exc:
            result[key] = {'error': clean(str(exc))}
    return result


if __name__ == '__main__':
    print(json.dumps(collect(), indent=2))
