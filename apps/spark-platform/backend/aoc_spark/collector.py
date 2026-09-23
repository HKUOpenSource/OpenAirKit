"""Fixed-source collector; only allowlisted device and service evidence leaves here."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from .domain import SCHEMA_VERSION, observation as obs, rate, utc
from .resources import Resources, radio_config
from .traffic import Traffic
from .connectivity import Reachability
from .telemetry import SchedulerFeed, RadioEvents
from .open5gs import Open5GS

STACKS = {
    "ocudu": {"unit": "aoc-v2-radio.service", "local": "172.28.81.1", "amf": "172.28.81.12",
              "bridge": "aoc-v2-open5gs-core",
              "containers": {n: "aoc-v2-open5gs-" + n + "-1" for n in
                             ("mongo", "nrf", "amf", "smf", "upf", "ausf", "udm", "udr",
                              "pcf", "bsf", "nssf", "ext-dn")}},
}


def run(argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.DEVNULL, timeout=8)


def n2_associated(raw, local, peer):
    return any("ESTAB" in line and peer + ":38412" in line.split() and
               any(re.fullmatch(re.escape(local) + r"(?:%[\w.-]+)?:\d+", f) for f in line.split())
               for line in raw.splitlines())


def systemd(raw):
    return {k: v for line in raw.splitlines() if "=" in line for k, v in [line.split("=", 1)]}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".tmp")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, "w") as out:
        json.dump(value, out, allow_nan=False)
    os.replace(pending, path)


def cpu_sample(raw, previous=None, capacity=None):
    fields = [int(value) for value in raw.splitlines()[0].split()[1:9]]
    total, idle = sum(fields), fields[3] + fields[4]
    usage = None
    if previous and total > previous[0]:
        usage = 1 - (idle - previous[1]) / (total - previous[0])
    capacity = capacity or os.cpu_count() or 1
    return (total, idle), usage, capacity


class Collector:
    def __init__(self, diagnostic_icmp=False):
        self.diagnostic_icmp = diagnostic_icmp
        self.previous = {}
        self.previous_services = {}
        self.events = []
        self.resources = Resources(run)
        self.traffic = Traffic(run)
        self.radio_events = RadioEvents()
        self.feed = SchedulerFeed()
        self.open5gs = Open5GS()
        self.devices = {}
        self.reachability = Reachability()
        self.pool = ThreadPoolExecutor(max_workers=4)

    def collect(self):
        values, services, units, properties = [], [], {}, {}
        for stack, spec in STACKS.items():
            try:
                state = systemd(run(["systemctl", "show", spec["unit"], "-p", "ActiveState", "-p", "SubState",
                                     "-p", "Result", "-p", "ExecMainStatus", "-p", "MainPID", "-p", "NRestarts",
                                     "-p", "InvocationID"]))
                properties[stack] = state
                units[stack] = state.get("ActiveState", "unknown")
                values.append(obs("host", stack, "radio_process", units[stack]))
                values.append(obs("host", stack, "radio_pid", int(state.get("MainPID", 0)), "count"))
                values.append(obs("host", stack, "restarts", int(state.get("NRestarts", 0)), "count"))
                if state.get("MainPID", "0") != "0":
                    values.extend(self.resources.process(int(state["MainPID"]), stack))
            except (OSError, ValueError, subprocess.SubprocessError):
                units[stack] = "unknown"
                values.append(obs("host", stack, "radio_process", status="unavailable", reason="systemd_read_failed"))
        active = [s for s, state in units.items() if state == "active"]
        stack_state = active[0] if len(active) == 1 else ("conflict" if len(active) > 1 else "none" if all(s == "inactive" for s in units.values()) else "unknown")
        try:
            sctp = run(["ss", "-H", "-n", "-A", "sctp"])
            for stack, spec in STACKS.items():
                values.append(obs("ran", stack, "n2_associated", n2_associated(sctp, spec["local"], spec["amf"])))
        except (OSError, subprocess.SubprocessError):
            for stack in STACKS:
                values.append(obs("ran", stack, "n2_associated", status="unavailable", reason="sctp_read_failed"))
        names = [name for spec in STACKS.values() for name in spec["containers"].values()]
        containers = {}
        try:
            # A missing container must not discard evidence for the remaining containers.
            raw = subprocess.run(["docker", "inspect", *names], capture_output=True, text=True, timeout=8)
            containers = {d["Name"].lstrip("/"): d for d in json.loads(raw.stdout or "[]")}
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        epochs = [containers.get(STACKS['ocudu']['containers'][role], {}).get('State', {}).get('StartedAt', 'missing')
                  for role in ('amf', 'smf')]
        core_epoch = hashlib.sha256('|'.join(epochs).encode()).hexdigest()[:16]
        core = self.open5gs.collect(core_epoch)
        values.extend(core['observations'])
        for stack, spec in STACKS.items():
            for role, name in spec["containers"].items():
                container = containers.get(name)
                state = container.get("State", {}) if container else {}
                health = state.get("Health", {}).get("Status")
                status = "ok" if container else "unavailable"
                service = dict(stack=stack, name=name, role=role, state=state.get("Status", "unknown"),
                               health=health or "unsupported", status=status,
                               exit_code=state.get("ExitCode"), restarts=container.get("RestartCount") if container else None)
                services.append(service)
                event_state = (service["state"], service["health"], service["exit_code"])
                if name in self.previous_services and event_state != self.previous_services[name]:
                    self.events.append(dict(id=hashlib.sha256((name + str(event_state) + utc()).encode()).hexdigest()[:24],
                                            at=utc(), stack=stack, entity=stack + ':' + role,
                                            level='error' if service['health'] == 'unhealthy' or service['exit_code'] not in (0, None) else 'info',
                                            kind="service_change", message=f'{name}: {service["state"]} / {service["health"]}'))
                self.previous_services[name] = event_state
            for metric, unit in (("dl_bps", "bit/s"), ("ul_bps", "bit/s"), ("dl_bler", "ratio"),
                                 ("ul_bler", "ratio"), ("cqi", "index"), ("dl_mcs", "index"),
                                 ("ul_mcs", "index"), ("sinr", "dB"), ("rrc_connected", "count"),
                                 ("dl_harq_nok", "count"), ("ul_harq_nok", "count")):
                values.append(obs("ran", stack, metric, unit=unit, status="unavailable", reason="metrics_stream_no_sample"))
        devices, components, links = list(core['devices']), [], []
        container_metrics = self.resources.containers(containers)
        for stack, spec in STACKS.items():
            epoch = properties.get(stack, {}).get("InvocationID", "none")
            sample = self.feed.get(epoch)
            if stack_state == stack:
                values.extend(self.feed.control_metrics())
            if sample and stack_state == stack:
                radio_devices, radio_values = sample
                # DU IDs and RNTIs have no guaranteed SUPI mapping; keep uncorrelated contexts separate.
                devices.extend(radio_devices)
                available = {v["name"] for v in radio_values}
                values = [v for v in values if not (v["entity"] == stack and v["source"] == "ran" and v["name"] in available)]
                values.extend(radio_values)
            config_path = "/var/lib/agentic-ocudu/v2/gnb.json"
            details=radio_config(config_path,stack)
            if units.get(stack)=='active':
                try:
                    values.extend(self.radio_events.read(stack,epoch))
                    exe=Path('/proc/{}/exe'.format(properties[stack]['MainPID'])).resolve(strict=True)
                    details['executable']=str(exe)
                    release=json.loads((exe.parent.parent/'release.json').read_text())
                    details['source_commit']=release.get('source_commit')
                    details['release_id']=release.get('release_id')
                except (OSError,ValueError,KeyError):
                    values.append(obs('ran',stack,'runtime_evidence',status='unavailable',reason='runtime_metadata_unreadable'))
            components.append(dict(id=stack + ":gnb", stack=stack, name="OCUDU gNB", kind="ran",
                                   state=units.get(stack, "unknown"), observed_at=utc(),
                                   details={**details, **{name: properties.get(stack, {}).get(name) for name in
                                                         ('SubState', 'Result', 'ExecMainStatus', 'InvocationID')}},
                                   metrics=[v for v in values if v["entity"] == stack and v['source'] in ('ran', 'host', 'resources')]))
            for service in [s for s in services if s["stack"] == stack]:
                name = service["name"]
                pid = containers.get(name, {}).get("State", {}).get("Pid", 0)
                metrics = [{**m,'entity':stack + ':' + service['role']} for m in container_metrics.get(name,[])]
                metrics += [m for m in values if m['entity'] == stack + ':' + service['role'] and m['source'] == 'open5gs_metrics']
                components.append(dict(id=stack + ":" + service["role"], stack=stack, name=service["role"].upper(),
                                       kind="nf", state=service["state"], health=service["health"], observed_at=utc(),
                                       details={"container": name, "pid": pid, "exit_code": service["exit_code"], "restarts": service["restarts"]}, metrics=metrics))
            traffic = self.traffic.collect(stack, containers.get(spec['containers']['upf'], {}))
            pfcp = False
            try:
                upf_pid = containers.get(spec['containers']['upf'], {}).get('State', {}).get('Pid', 0)
                if upf_pid:
                    sockets = Path('/proc/{}/net/udp'.format(upf_pid)).read_text().splitlines()[1:]
                    pfcp = any(line.split()[1].endswith(':2265') for line in sockets)
            except (OSError, IndexError):
                pass
            for protocol in ("n2", "n3", "n4", "n6"):
                n2 = next((v for v in values if v["name"] == "n2_associated" and v["entity"] == stack), None)
                n3 = next((v for v in values if v['name'] == 'active_session_paths' and v['entity'] == stack + ':n3'), None)
                smf_pfcp = next((v for v in values if v['name'] == 'pfcp_peers' and v['entity'] == stack + ':smf'), None)
                upf_pfcp = next((v for v in values if v['name'] == 'pfcp_peers' and v['entity'] == stack + ':upf'), None)
                state = 'unknown'
                if protocol == 'n2' and n2 and n2['status'] == 'ok':
                    state = 'healthy' if n2['value'] else 'unavailable'
                elif protocol == 'n3' and n3 and n3['status'] == 'ok':
                    state = 'healthy' if n3['value'] > 0 else 'inactive'
                elif protocol == 'n4' and smf_pfcp and upf_pfcp and smf_pfcp['status'] == upf_pfcp['status'] == 'ok':
                    state = 'healthy' if smf_pfcp['value'] > 0 and upf_pfcp['value'] > 0 else 'inactive'
                elif protocol == 'n6' and traffic.get('n6'):
                    state = 'healthy' if all(item['status'] == 'ok' for item in traffic['n6']) else 'unknown'
                links.append(dict(id=stack + ":" + protocol, stack=stack, name=protocol.upper(), kind="link", observed_at=utc(),
                                  state=state,
                                  details={"evidence": "sctp_association" if protocol == "n2" else 'pfcp_udp_listener_not_association' if protocol == 'n4' and pfcp else 'independent_ip_counters' if traffic.get(protocol) else "protocol_evidence_unavailable",
                                           **({'open5gs_info': core['gnb']} if protocol == 'n2' and core['gnb'] else {})},
                                  metrics=traffic.get(protocol, [])))
        self.host(values)
        values.extend(self.resources.host())
        for stack in STACKS:
            components.append(dict(id=stack + ':bridge', stack=stack, name='Core bridge (diagnostic)', kind='interface',
                                   state='unknown', observed_at=utc(), details={'interface': STACKS[stack]['bridge']},
                                   metrics=[v for v in values if v['entity'] == stack and v['name'].startswith('bridge_')]))
        if self.diagnostic_icmp and stack_state in STACKS:
            self.reachability.collect(devices, stack_state, properties.get(stack_state, {}).get('InvocationID'))
        else:
            self.reachability.cache.clear()
        for device in devices:
            previous = self.devices.get(device['id'])
            if previous:
                device['first_seen'] = previous.get('first_seen', previous['observed_at'])
                before = {(s['id'], s['dnn'], s['address']) for s in previous.get('sessions', [])}
                after = {(s['id'], s['dnn'], s['address']) for s in device.get('sessions', [])}
                if before != after or previous.get('state') != device.get('state'):
                    at = utc()
                    self.events.append(dict(id=hashlib.sha256((device['id'] + at).encode()).hexdigest()[:24], at=at,
                                            stack=device['stack'], entity=device['id'], level='info', kind='device_change',
                                            message=('Subscriber ****' + device['identity'][-4:] if device['identity'].isdecimal() else device['identity']) + ': registration/session evidence changed'))
                old_probe = previous.get('reachability', {}).get('state', 'unknown')
                new_probe = device.get('reachability', {}).get('state', 'unknown')
                if old_probe != new_probe:
                    at = utc()
                    self.events.append(dict(id=hashlib.sha256((device['id'] + 'probe' + at).encode()).hexdigest()[:24], at=at,
                                            stack=device['stack'], entity=device['id'], level='info', kind='ue_address_probe_change',
                                            message='Spark ext-DN ICMP diagnostic: ' + new_probe))
        missing = set(self.devices) - {d['id'] for d in devices}
        for identifier in missing:
            prior, at = self.devices[identifier], utc()
            self.events.append(dict(id=hashlib.sha256((identifier + at).encode()).hexdigest()[:24], at=at,
                                    stack=prior['stack'], entity=identifier, level='info', kind='device_evidence_expired',
                                    message='Device evidence no longer observed; connectivity unknown'))
        self.devices = {d["id"]: d for d in devices}
        components.append(dict(id="spark", stack="host", name="DGX Spark", kind="host", state="unknown",
                               observed_at=utc(), details={}, metrics=[v for v in values if v["entity"] == "spark"]))
        for device in devices:
            device.setdefault("first_seen", device["observed_at"])
        from .domain import fresh_snapshot
        self.events = self.events[-100:]
        return fresh_snapshot(dict(schema_version=SCHEMA_VERSION, observed_at=utc(), collector_status="ok", active_stack=stack_state,
                                   observations=values, services=services, events=self.events, components=components, links=links, devices=devices))

    def host(self, values):
        now = time.monotonic()
        try:
            current, usage, capacity = cpu_sample(Path("/proc/stat").read_text(), self.previous.get("cpu"))
            self.previous["cpu"] = current
            values.append(obs("host", "spark", "cpu_capacity", capacity, "cores"))
            values.append(obs("host", "spark", "cpu_cores", usage * capacity if usage is not None else None, "cores",
                              "ok" if usage is not None else "unavailable", None if usage is not None else "sampling_warmup"))
            values.append(obs("host", "spark", "cpu_usage", usage, "ratio", "ok" if usage is not None else "unavailable", None if usage is not None else "sampling_warmup"))
            mem = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith(("MemTotal:", "MemAvailable:"))}
            values.append(obs("host", "spark", "memory_used", mem["MemTotal"] - mem["MemAvailable"], "byte"))
            values.append(obs("host", "spark", "memory_total", mem["MemTotal"], "byte"))
            for stack, spec in STACKS.items():
                for direction in ("rx", "tx"):
                    path = Path("/sys/class/net") / spec["bridge"] / "statistics" / (direction + "_bytes")
                    if not path.exists():
                        values.append(obs("host", stack, "bridge_" + direction, unit="bit/s", status="unavailable", reason="interface_absent"))
                        continue
                    count = int(path.read_text())
                    key = (stack, direction)
                    old = self.previous.get(key)
                    speed = rate(old[0], count, now - old[1]) if old else None
                    self.previous[key] = (count, now)
                    values.append(obs("host", stack, "bridge_" + direction, speed, "bit/s", "ok" if speed is not None else "unavailable", None if speed is not None else "warmup_or_counter_reset", now - old[1] if old else None))
        except (OSError, ValueError, KeyError):
            values.append(obs("host", "spark", "host_metrics", status="unavailable", reason="procfs_read_failed"))
        try:
            devices = [p for p in Path("/sys/bus/usb/devices").glob("*") if (p / "idVendor").exists() and
                       (p / "idVendor").read_text().strip() == "2500" and (p / "idProduct").read_text().strip() == "0020"]
            values.append(obs("host", "spark", "b210_devices", len(devices), "count"))
            if len(devices) == 1:
                device = devices[0]
                for field in ("speed", "serial", "product"):
                    if (device / field).exists():
                        values.append(obs("host", "spark", "b210_" + field, (device / field).read_text().strip()))
                node = "/dev/bus/usb/{:03d}/{:03d}".format(int((device / "busnum").read_text()), int((device / "devnum").read_text()))
                if os.geteuid() == 0:
                    result = subprocess.run(["fuser", node], capture_output=True, text=True, timeout=3)
                    if result.returncode not in (0, 1):
                        raise ValueError("fuser_failed")
                    pids = [int(s) for s in result.stdout.split() if s.isdigit()]
                    values.append(obs("host", "spark", "b210_holder_pids", pids))
                else:
                    values.append(obs("host", "spark", "b210_holder_pids", status="unavailable", reason="requires_privileged_collector"))
        except (OSError, ValueError, subprocess.SubprocessError):
            values.append(obs("host", "spark", "b210_holder_pids", status="unavailable", reason="usb_inspection_failed"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--diagnostic-icmp", action="store_true", help="Enable bounded ext-DN ICMP diagnostics; does not affect network health")
    args = parser.parse_args()
    collector = Collector(diagnostic_icmp=args.diagnostic_icmp)
    while True:
        atomic_json(args.output, collector.collect())
        if args.once:
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
