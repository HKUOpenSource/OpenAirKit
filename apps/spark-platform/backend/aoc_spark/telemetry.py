"""Version-specific, bounded telemetry readers. Only normalized allowlisted fields leave this module."""
import copy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time

from .domain import observation, utc, age_seconds


def device_id(stack, identity):
    return stack + ":ue:" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def number(value, minimum=0):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= minimum:
        return value
    return None


def parse_ocudu(payload, epoch, received_at=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
        return None
    at = received_at or utc()
    devices, values = [], []
    for cell in payload["cells"]:
        if not isinstance(cell, dict) or not isinstance(cell.get("cell_metrics"), dict):
            raise ValueError("invalid_scheduler_cell")
        pci = cell["cell_metrics"].get("pci")
        for ue in cell.get("ue_list", []):
            if not isinstance(ue, dict) or number(ue.get("rnti")) is None:
                raise ValueError("invalid_scheduler_ue")
            rnti = str(ue["rnti"])
            key = device_id("ocudu", epoch + ":" + str(pci) + ":" + rnti)
            metrics = []
            transport = {}
            for direction in ("dl", "ul"):
                ok, nok = number(ue.get(direction + "_nof_ok")), number(ue.get(direction + "_nof_nok"))
                transport[direction] = (ok, nok, ok + nok if ok is not None and nok is not None else None)
            fields = (("dl_brate", "dl_bps", "bit/s"), ("ul_brate", "ul_bps", "bit/s"),
                      ("cqi", "cqi", "index"), ("dl_mcs", "dl_mcs", "index"),
                      ("ul_mcs", "ul_mcs", "index"), ("pusch_snr_db", "sinr", "dB"),
                      ("pusch_rsrp_db", "pusch_rsrp", "dB"), ("phr", "phr", "dB"),
                      ("dl_ri", "dl_rank", "index"), ("ul_ri", "ul_rank", "index"))
            for source, name, unit in fields:
                value = number(ue.get(source), -100 if unit == "dB" else 0)
                direction = name[:2] if name.startswith(("dl_", "ul_")) else None
                if (direction and transport[direction][2] == 0
                        and (name == direction + "_mcs" or name == direction + "_bps" and value != 0)):
                    value, reason = None, "no_transport_blocks"
                else:
                    reason = None if value is not None else "scheduler_field_absent"
                metrics.append({**observation("ocudu_scheduler", key, name, value, unit,
                                             "ok" if value is not None else "unavailable",
                                             reason), "observed_at": at})
            for direction in ("dl", "ul"):
                ok, nok, reported_total = transport[direction]
                total = reported_total or 0
                metrics.append({**observation("ocudu_scheduler", key, direction + "_bler", nok / total if total else None,
                                             "ratio", "ok" if total else "unavailable", None if total else "no_transport_blocks"), "observed_at": at})
                for result, count in (("ok", ok), ("nok", nok)):
                    metrics.append({**observation("ocudu_scheduler", key, direction + "_harq_" + result, count,
                                                  "count", "ok" if count is not None else "unavailable",
                                                  "scheduler_report_window" if count is not None else "scheduler_field_absent"),
                                    "observed_at": at})
            devices.append(dict(id=key, stack="ocudu", epoch=epoch, identity="RNTI " + format(int(rnti), "04x"),
                                identifiers={"rnti": format(int(rnti), "04x"), "pci": pci, "du_ue_id": ue.get("ue")},
                                registration="unknown", state="radio_observed", status="ok", observed_at=at,
                                source="ocudu_scheduler", correlation="radio_only", metrics=metrics, sessions=[]))
    for name in ("dl_bps", "ul_bps", "dl_harq_ok", "dl_harq_nok", "ul_harq_ok", "ul_harq_nok"):
        parts = [m["value"] for d in devices for m in d["metrics"] if m["name"] == name]
        valid = bool(parts) and all(v is not None for v in parts)
        values.append({**observation("ran", "ocudu", name, sum(parts) if valid else None, "bit/s",
                                     "ok" if valid else "unavailable", None if valid else "scheduler_field_absent"), "observed_at": at})
        if name.endswith(('_ok', '_nok')):
            values[-1]['unit'] = 'count'
            values[-1]['reason'] = 'sum_of_per_ue_scheduler_window' if valid else values[-1]['reason']
    for name in ("cqi", "dl_mcs", "ul_mcs", "dl_bler", "ul_bler", "sinr", "pusch_rsrp", "phr", "dl_rank", "ul_rank"):
        parts = [m["value"] for d in devices for m in d["metrics"] if m["name"] == name and m["value"] is not None]
        unit = next((m['unit'] for d in devices for m in d['metrics'] if m['name'] == name), 'index')
        values.append({**observation("ran", "ocudu", name, sum(parts) / len(parts) if parts else None, unit,
                                     "ok" if parts else "unavailable", "mean_of_current_ue_reports" if parts else "scheduler_field_absent"),
                       "observed_at": at})
    values.append({**observation("ran", "ocudu", "rrc_connected", None, "count", "unavailable",
                                 "current_rrc_state_not_reported"), "observed_at": at})
    values.append({**observation("ran", "ocudu", "radio_contexts", len(devices), "count"), "observed_at": at})
    return devices, values


class RadioIdentity:
    """A reused temporary radio identifier must start a new observation history."""
    def __init__(self):
        self.current = {}

    def apply(self, devices, complete=False):
        seen = set()
        for device in devices:
            base = device['id']
            seen.add(base)
            identifiers = device['identifiers']
            explicit = identifiers.get('cu_ue_id', identifiers.get('du_ue_id'))
            old = self.current.get(base)
            gap = age_seconds(old['at'], datetime.fromisoformat(device['observed_at'])) if old else None
            if not old or gap is None or not 0 <= gap <= 20 or (explicit is not None and old['explicit'] is not None and explicit != old['explicit']):
                old = dict(id=device_id(device['stack'], base + ':' + device['observed_at']),
                           first_seen=device['observed_at'], explicit=explicit)
            old.update(at=device['observed_at'], explicit=explicit if explicit is not None else old['explicit'])
            self.current[base] = old
            device.update(id=old['id'], first_seen=old['first_seen'])
            for metric in device['metrics']:
                metric['entity'] = old['id']
            if device.get('state') == 'released':
                self.current.pop(base, None)
        if complete:
            self.current = {key: value for key, value in self.current.items() if key in seen}
        return devices


class SchedulerFeed:
    def __init__(self):
        self.lock = threading.Lock()
        self.sample = None
        self.control = []
        self.epoch = "unknown"
        self.started = False

    def start(self):
        if not self.started:
            self.started = True
            threading.Thread(target=self.receive, daemon=True).start()

    def receive(self):
        from websockets.sync.client import connect
        while True:
            try:
                with connect("ws://127.0.0.1:8001", open_timeout=2, max_size=2**20, close_timeout=1) as connection:
                    identities = RadioIdentity()
                    with self.lock:
                        epoch = self.epoch
                    connection.send(json.dumps({"cmd": "metrics_subscribe"}))
                    while True:
                        data = json.loads(connection.recv(timeout=10))
                        sample = parse_ocudu(data, epoch)
                        if sample is not None:
                            identities.apply(sample[0], complete=True)
                        with self.lock:
                            if self.epoch != epoch:
                                break
                            if sample is not None:
                                self.sample = sample
                            if isinstance(data,dict) and isinstance(data.get('cu-cp'),dict):
                                self.control = parse_control(data)
            except Exception as exc:
                # No exception text: a decoder exception can contain the raw payload.
                del exc
                time.sleep(3)

    def get(self, epoch):
        self.start()
        with self.lock:
            if epoch != self.epoch:
                self.epoch, self.sample = epoch, None
                self.control = []
            return copy.deepcopy(self.sample)

    def control_metrics(self):
        with self.lock:
            return copy.deepcopy(self.control)


def parse_control(payload):
    cp=payload['cu-cp'];values=[]
    dus=cp.get('rrcs',{}).get('du',[])
    for source,name in (('mean_nof_rrc_connections','rrc_mean_connections'),('max_nof_rrc_connections','rrc_peak_connections')):
        parts=[number(d.get('rrc_connection_number',{}).get(source)) for d in dus]
        valid=bool(parts) and all(v is not None for v in parts)
        values.append(observation('ran','ocudu',name,sum(parts) if valid else None,'count','ok' if valid else 'unavailable',
                                  'reported_window_mean' if 'mean' in name else 'sum_of_per_du_window_maxima'))
    return values


class RadioEvents:
    def __init__(self):
        self.cursors={}

    def read(self,stack,epoch):
        if stack != 'ocudu':
            raise ValueError('invalid_stack')
        path=Path('/var/log/agentic-ocudu/v2/gnb.log')
        stat=path.stat();token=(epoch,stat.st_ino);now=time.monotonic()
        old=self.cursors.get(stack)
        if not old or old[0]!=token or stat.st_size<old[1]:
            self.cursors[stack]=(token,stat.st_size,now)
            return []
        if stat.st_size-old[1]>1024*1024:
            self.cursors[stack]=(token,stat.st_size,now)
            return [observation('ran',stack,'radio_log_events',status='unavailable',reason='log_reader_overrun')]
        with path.open('rb') as stream:
            stream.seek(old[1]);raw=stream.read(1024*1024).decode(errors='replace')
        self.cursors[stack]=(token,stat.st_size,now)
        return [observation('ran',stack,'log_'+name,len(re.findall(pattern,raw,re.I)),'count',reason='log_event_count',window=now-old[2])
                for name,pattern in [('underflows',r'\bunderflow\b'),('overflows',r'\boverflow\b'),('lates',r'\blate (?:command|packet)\b')]]
