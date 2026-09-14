"""Reviewed first-RF profile and independent production release staging."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from .core import write_json


PROFILE = {"schema_version": 1, "reviewed": True, "rf_accepted": False, "serial": None,
           "dl_arfcn": 643392, "pci": 666, "band": 78, "bandwidth_mhz": 20,
           "scs_khz": 30, "srate_msps": 23.04, "tx_gain": 80, "rx_gain": 68,
           "clock": "internal", "tdd_period_slots": 10, "dl_slots": 7, "dl_symbols": 6,
           "ul_slots": 2, "ul_symbols": 4}


def validate_profile(profile, serial_required=True):
    if profile.get("reviewed") is not True:
        raise ValueError("RF profile has not been reviewed")
    for field, value in PROFILE.items():
        if field not in ("serial", "rf_accepted") and profile.get(field) != value:
            raise ValueError("RF profile differs from the reviewed first-access parameters: " + field)
    serial = profile.get("serial")
    if (serial_required or serial is not None) and not re.fullmatch(r"[A-Za-z0-9]{1,32}", serial or ""):
        raise ValueError("A probed UHD serial is required")


def gnb_config(config, profile):
    validate_profile(profile)
    radio, addr = config["radio"], config["network"]["addresses"]
    if (radio["plmn"], radio["tac"], radio["sst"]) != ("46003", 1, 1):
        raise ValueError("Core does not match the reviewed lab PLMN/TAC/SST")
    return {"cu_cp": {"amf": {"addrs": addr["amf"], "port": 38412, "bind_addrs": addr["gnb"],
            "supported_tracking_areas": [{"tac": 1, "plmn_list": [{"plmn": "46003",
                "tai_slice_support_list": [{"sst": 1}]}]}]}},
        "cu_up": {"ngu": {"socket": [{"bind_addr": addr["gnb"]}]}},
        "ru_sdr": {"device_driver": "uhd", "device_args": "type=b200,serial=" + profile["serial"] +
                    ",num_recv_frames=64,num_send_frames=64", "srate": profile["srate_msps"], "otw_format": "sc12",
                    "clock": "internal", "sync": "internal", "tx_gain": profile["tx_gain"], "rx_gain": profile["rx_gain"]},
        "cell_cfg": {"dl_arfcn": profile["dl_arfcn"], "band": 78, "channel_bandwidth_MHz": 20,
                     "common_scs": 30, "plmn": "46003", "tac": 1, "pci": profile["pci"],
                     "nof_antennas_dl": 1, "nof_antennas_ul": 1,
                     "tdd_ul_dl_cfg": {"dl_ul_tx_period": 10, "nof_dl_slots": 7, "nof_dl_symbols": 6,
                                       "nof_ul_slots": 2, "nof_ul_symbols": 4}},
        **({"remote_control": {"enabled": True, "bind_addr": "127.0.0.1", "port": 8001},
            "metrics": {"enable_json": True}} if profile.get("telemetry_enabled") is True else {"remote_control": {"enabled": False}}),
        "log": {"filename": "/var/log/agentic-ocudu/gnb.log", "all_level": "info"},
        "pcap": {"mac_enable": False, "ngap_enable": False}}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(config, bundle, build_result, probe, output):
    from .cli import ROOT, compose_args
    compose_args(config, bundle)
    result = json.loads(build_result.read_text())
    binary = Path(result["binary"])
    if result["commit"] != "050a2bb72e1d794cd60570d809987c1fcda3e54b" or digest(binary) != result["sha256"]:
        raise ValueError("OCUDU build does not match the verified artifact")
    if not probe.is_file():
        raise ValueError("Compile the independent B210 probe before staging")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    release = output / "release"
    release.mkdir()
    for folder in ("scripts", "config", "deploy"):
        shutil.copytree(ROOT / folder, release / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (release / "bin").mkdir()
    shutil.copy2(binary, release / "bin/gnb")
    shutil.copy2(probe, release / "bin/probe-b210")
    shutil.copytree(bundle, output / "core", symlinks=True)
    if any(path.is_symlink() for path in output.rglob("*")):
        raise ValueError("Release inputs must not contain symlinks")
    write_json(output / "spark.json", config)
    write_json(output / "radio.json", PROFILE)
    candidate = dict(PROFILE, serial="AOCPARSEONLY")
    write_json(output / "parse-only.json", gnb_config(config, candidate))
    subprocess.run([str(binary), "--dryrun", "-c", str(output / "parse-only.json")], check=True, timeout=30)
    files = {str(path.relative_to(release)): digest(path) for path in sorted(release.rglob("*")) if path.is_file()}
    release_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    write_json(output / "release.json", {"schema_version": 1, "release_id": release_id, "files": files,
               "source_commit": result["commit"], "old_bundle": str(bundle), "rf_accepted": False})
    print("Production package staged without RF access: " + str(output))
