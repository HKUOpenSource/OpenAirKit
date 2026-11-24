"""Read-only process, container and hardware observations."""
import json
import os
from pathlib import Path
import re
import time
import subprocess

from .domain import observation as obs, rate


def bytes_value(value):
    match=re.fullmatch(r'\s*([\d.]+)\s*(B|kB|KB|MB|GB|TB|KiB|MiB|GiB|TiB)\s*',value)
    if not match:
        raise ValueError('invalid_byte_unit')
    powers={'B':1,'kB':1000,'KB':1000,'MB':1000**2,'GB':1000**3,'TB':1000**4,'KiB':1024,'MiB':1024**2,'GiB':1024**3,'TiB':1024**4}
    return float(match[1])*powers[match[2]]


class Resources:
    def __init__(self, run):
        self.run = run
        self.previous = {}
        self.container_cache = (None, {})

    def containers(self, inspected):
        now=time.monotonic()
        if self.container_cache[0] is not None and now-self.container_cache[0]<10:
            return self.container_cache[1]
        names=[name for name,c in inspected.items() if c.get('State',{}).get('Running')]
        if not names:
            return {}
        try:
            command=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*names],capture_output=True,text=True,timeout=8)
            result={}
            for line in command.stdout.splitlines():
                row=json.loads(line); name=row['Name']
                if name not in inspected:
                    continue
                cores=float(row['CPUPerc'].rstrip('%'))/100
                used,limit=[bytes_value(v) for v in row['MemUsage'].split('/')]
                host=inspected[name].get('HostConfig',{})
                quota=host.get('NanoCpus',0)/1e9
                if not quota and host.get('CpuQuota',0)>0 and host.get('CpuPeriod',0)>0:
                    quota=host['CpuQuota']/host['CpuPeriod']
                affinity=host.get('CpusetCpus','')
                capacity=os.cpu_count()
                if affinity:
                    cpus=set()
                    for item in affinity.split(','):
                        ends=item.split('-');cpus.update(range(int(ends[0]),int(ends[-1])+1))
                    capacity=min(capacity,len(cpus))
                if quota:
                    capacity=min(capacity,quota)
                pairs={'cpu_cores':(cores,'cores'),'cpu_capacity':(capacity,'cores'),'cpu_utilization':(cores/capacity if capacity else None,'ratio'),
                       'cpu_host_share':(cores/os.cpu_count(),'ratio'),'memory_used':(used,'byte'),'memory_total':(limit,'byte')}
                result[name]=[obs('docker_stats',name,k,v,unit) for k,(v,unit) in pairs.items()]
            self.container_cache=(now,result)
            return result
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):
            return {}

    def process(self, pid, entity):
        values = []
        try:
            proc = Path('/proc') / str(int(pid))
            fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            ticks, start = int(fields[11]) + int(fields[12]), int(fields[19])
            capacity = len(os.sched_getaffinity(int(pid)))
            now = time.monotonic()
            token = (pid, start)
            old = self.previous.get(entity)
            cores = ((ticks - old[2]) / os.sysconf('SC_CLK_TCK') / (now - old[1])
                     if old and old[0] == token and now > old[1] and ticks >= old[2] else None)
            self.previous[entity] = (token, now, ticks)
            stats = {
                'cpu_cores': (cores, 'cores'), 'cpu_capacity': (capacity, 'cores'),
                'cpu_utilization': (cores / capacity if cores is not None and capacity else None, 'ratio'),
                'cpu_host_share': (cores / os.cpu_count() if cores is not None else None, 'ratio'),
                'memory_used': (int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), 'byte'),
                'uptime': (float(Path('/proc/uptime').read_text().split()[0]) - start / os.sysconf('SC_CLK_TCK'), 'seconds')}
            for name, (value, unit) in stats.items():
                values.append(obs('resources', entity, name, value, unit, 'ok' if value is not None else 'unavailable'))
        except (OSError, ValueError, IndexError):
            values.append(obs('resources', entity, 'process_resources', status='unavailable', reason='process_absent_or_unreadable'))
        return values

    def container(self, name, entity):
        try:
            raw = self.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', name])
            row = json.loads(raw)
            cpu = float(row['CPUPerc'].rstrip('%')) / 100
            # Docker CPU% is per core, unlike host utilization.
            return [obs('docker_stats', entity, 'cpu_cores', cpu, 'cores'),
                    obs('docker_stats', entity, 'cpu_host_share', cpu / os.cpu_count(), 'ratio')]
        except (OSError, ValueError, KeyError):
            return []

    def host(self):
        values = []
        try:
            routes=[row.split() for row in Path('/proc/net/route').read_text().splitlines()[1:]]
            candidates=[r for r in routes if len(r)>7 and r[1]=='00000000' and int(r[3],16)&1]
            interface=min(candidates,key=lambda r:int(r[6]))[0] if candidates else None
            if interface:
                now=time.monotonic()
                values.append(obs('host','spark','default_interface',interface))
                for direction in ('rx','tx'):
                    count=int((Path('/sys/class/net')/interface/'statistics'/(direction+'_bytes')).read_text())
                    key=('host',interface,direction);old=self.previous.get(key)
                    elapsed=now-old[0] if old else None
                    speed=rate(old[1],count,elapsed) if old else None
                    self.previous[key]=(now,count)
                    values.append(obs('host','spark','host_'+direction,speed,'bit/s','ok' if speed is not None else 'unavailable',
                                      'default_route_interface_not_ue_throughput',elapsed))
        except (OSError,ValueError,IndexError):
            values.append(obs('host','spark','default_interface',status='unavailable'))
        try:
            fs = os.statvfs('/var/lib')
            values += [obs('host', 'spark', 'disk_used', (fs.f_blocks - fs.f_bfree) * fs.f_frsize, 'byte'),
                       obs('host', 'spark', 'disk_total', fs.f_blocks * fs.f_frsize, 'byte')]
        except OSError:
            values.append(obs('host', 'spark', 'disk_used', status='unavailable'))
        temperatures = []
        for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
            try:
                value = int(path.read_text()) / 1000
                if -20 <= value <= 150:
                    temperatures.append(value)
            except (OSError, ValueError):
                continue
        values.append(obs('host', 'spark', 'temperature', max(temperatures) if temperatures else None, 'C',
                          'ok' if temperatures else 'unsupported', 'maximum_thermal_zone' if temperatures else 'no_thermal_sensor'))
        return values


def radio_config(path, stack):
    """Explicit configuration fields only; never serialize credentials or entire config files."""
    if stack != 'ocudu':
        return {}
    try:
        raw = json.loads(Path(path).read_text())
        cell, ru = raw.get('cell_cfg', {}), raw.get('ru_sdr', {})
        result = {k: cell[k] for k in ('plmn', 'tac', 'pci', 'band', 'dl_arfcn', 'channel_bandwidth_MHz',
                                       'common_scs', 'nof_antennas_dl', 'nof_antennas_ul') if k in cell}
        result.update({k: ru[k] for k in ('srate', 'clock', 'tx_gain', 'rx_gain') if k in ru})
        result['tdd'] = cell.get('tdd_ul_dl_cfg')
        return result
    except (OSError, ValueError, TypeError):
        return {}
