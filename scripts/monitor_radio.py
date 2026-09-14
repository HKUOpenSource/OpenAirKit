#!/usr/bin/env python3
"""Explicit radio telemetry upgrade, with immutable release and rollback backup."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

INSTALL = Path('/opt/agentic-ocudu')
CONFIG = Path('/etc/agentic-ocudu')
BACKUP = Path('/var/lib/aoc-radio-upgrade')
UNITS = ('aoc-core.service','aoc-gnb.service','aoc-stack.target')


def call(argv, timeout=360):
    subprocess.run(argv, check=True, timeout=timeout)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def switch_pointer(release):
    pending=INSTALL/'.current-telemetry'
    pending.unlink(missing_ok=True)
    pending.symlink_to(release)
    os.replace(pending,INSTALL/'current')


def runtime(release):
    spec=importlib.util.spec_from_file_location('aoc_upgrade_runtime',release/'scripts/radio_runtime.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_monitor(package):
    manifest=json.loads((package/'manifest.json').read_text())
    for name in ('radio-config.py','radio-guard.py','radio-upgrade.py'):
        if sha(package/name)!=manifest['files'][name]:
            raise ValueError('Telemetry package checksum differs')


def load_renderer(package):
    spec=importlib.util.spec_from_file_location('scripts.aoclib.monitor_renderer',package/'radio-config.py')
    renderer=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    return renderer


def restore(saved):
    old=Path(saved['release'])
    if old.parent != INSTALL/'releases':
        raise ValueError('Invalid rollback release')
    for name in UNITS:
        shutil.copyfile(BACKUP/name,Path('/etc/systemd/system')/name)
    for name in ('radio.json','ocudu/gnb.json'):
        shutil.copyfile(BACKUP/name,CONFIG/name)
    switch_pointer(old)
    call(['systemctl','daemon-reload'])
    guard_unit=Path('/etc/systemd/system/aoc-metrics-guard.service')
    if guard_unit.exists():
        call(['systemctl','stop','aoc-metrics-guard.service'])
        guard_unit.unlink()
    exists=subprocess.run(['nft','list','table','inet','aoc_metrics_guard'],capture_output=True,timeout=5)
    if exists.returncode == 0:
        call(['nft','delete','table','inet','aoc_metrics_guard'])
    call(['systemctl','daemon-reload'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('enable','rollback'))
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise SystemExit('Run this step in the Spark sudo terminal; it interrupts data and IMS')
    package=Path(__file__).resolve().parent
    verify_monitor(package)
    current=(INSTALL/'current').resolve(strict=True)
    old=runtime(current)
    config=old.verify_release()
    job=Path('/var/lib/aoc-switch/job.json')
    if job.exists() and json.loads(job.read_text()).get('status')=='running':
        raise ValueError('Wait for the current switch task')
    if old.show('aoc-gnb.service').get('ActiveState')!='active':
        raise ValueError('Switch to OCUDU first; this upgrade does not take the radio from OAI')
    if args.action=='rollback':
        saved=json.loads((BACKUP/'state.json').read_text())
        with old.switch_lock():
            old.stop(config)
            old.usb_free()
            restore(saved)
        call(['/usr/bin/python3','-I',str(INSTALL/'current/scripts/radio_runtime.py'),'start'])
        print('Previous radio restored; Jetson reconnection remains manual')
        return
    if (BACKUP/'state.json').exists():
        raise ValueError('Existing telemetry transaction retained; inspect it before another upgrade')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',8001))
    call(['nft','--version'])
    if Path('/etc/systemd/system/aoc-metrics-guard.service').exists():
        raise ValueError('Existing metrics guard unit has no upgrade transaction')
    if subprocess.run(['nft','list','table','inet','aoc_metrics_guard'],capture_output=True,timeout=5).returncode == 0:
        raise ValueError('Existing metrics guard table has no upgrade transaction')
    BACKUP.mkdir(mode=0o700,parents=True,exist_ok=True)
    (BACKUP/'ocudu').mkdir(mode=0o700,exist_ok=True)
    for name in UNITS:
        shutil.copyfile(Path('/etc/systemd/system')/name,BACKUP/name)
    for name in ('radio.json','ocudu/gnb.json'):
        shutil.copyfile(CONFIG/name,BACKUP/name)
    saved={'release':str(current),'at':time.time(),'phase':'prepared'}
    (BACKUP/'state.json').write_text(json.dumps(saved))
    manifest=json.loads((current/'release.json').read_text())
    fingerprint=hashlib.sha256((manifest['release_id']+sha(package/'radio-config.py')+sha(package/'radio-guard.py')).encode()).hexdigest()[:16]
    release=INSTALL/'releases'/('monitor-'+fingerprint)
    shutil.copytree(current,release,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(package/'radio-config.py',release/'scripts/aoclib/radio.py')
    shutil.copyfile(package/'radio-guard.py',release/'scripts/monitor_radio_guard.py')
    guard_name='aoc-metrics-guard.service'
    guard='[Unit]\nDescription=OCUDU local metrics access guard\nBefore=aoc-gnb.service\n\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/usr/bin/python3 '+str(release/'scripts/monitor_radio_guard.py')+'\n'
    rendered={name:(BACKUP/name).read_text().replace(str(current),str(release)) for name in UNITS}
    rendered['aoc-gnb.service']=rendered['aoc-gnb.service'].replace('[Unit]\n','[Unit]\nRequires='+guard_name+'\nAfter='+guard_name+'\n',1)
    rendered[guard_name]=guard
    units=release/'telemetry-units';units.mkdir()
    for name,body in rendered.items():
        (units/name).write_text(body)
    call(['systemd-analyze','verify',*[str(units/name) for name in rendered]])
    manifest['files']={str(p.relative_to(release)):sha(p) for p in release.rglob('*') if p.is_file() and p.name!='release.json'}
    manifest['release_id']=release.name
    manifest['units']={name:hashlib.sha256(body.encode()).hexdigest() for name,body in rendered.items()}
    (release/'release.json').write_text(json.dumps(manifest,indent=2))
    profile=json.loads((CONFIG/'radio.json').read_text());profile['telemetry_enabled']=True
    renderer=load_renderer(package)
    candidate=renderer.gnb_config(config,profile)
    (BACKUP/'candidate.json').write_text(json.dumps(candidate))
    call([str(release/'bin/gnb'),'--dryrun','-c',str(BACKUP/'candidate.json')],30)
    call(['/usr/bin/python3',str(release/'scripts/monitor_radio_guard.py')],15)
    try:
        with old.switch_lock():
            old.stop(config)
            old.usb_free()
            for name in rendered:
                shutil.copyfile(units/name,Path('/etc/systemd/system')/name)
            (CONFIG/'radio.json').write_text(json.dumps(profile))
            (CONFIG/'ocudu/gnb.json').write_text(json.dumps(candidate))
            switch_pointer(release)
            call(['systemctl','daemon-reload'])
        call(['/usr/bin/python3','-I',str(release/'scripts/radio_runtime.py'),'start'])
        saved.update(phase='enabled',new_release=str(release))
        (BACKUP/'state.json').write_text(json.dumps(saved))
        print('OCUDU telemetry enabled at 127.0.0.1:8001; verify Jetson data and IMS sessions')
    except Exception:
        with old.switch_lock():
            old.stop(config)
            old.usb_free()
            restore(saved)
        call(['/usr/bin/python3','-I',str(current/'scripts/radio_runtime.py'),'start'])
        print('Telemetry upgrade failed; previous radio process restored. UE sessions require verification.',file=sys.stderr)
        raise


if __name__=='__main__':
    main()
