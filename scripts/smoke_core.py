#!/usr/bin/env python3
"""Bounded core service checks; these do not prove UE or IMS PDU connectivity."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.aoclib.cli import compose_args, core_healthy, core_states
from scripts.aoclib.core import write_json


def check(config, bundle):
    argv = compose_args(config, bundle)
    states = core_states(argv)
    if not core_healthy(states):
        raise ValueError("All ten core/IMS services must be healthy")

    def inside(service, *command):
        return subprocess.check_output(argv + ["exec", "-T", service, *command], text=True, timeout=30)

    addr = config["network"]["addresses"]
    nat = inside("upf", "iptables", "-t", "nat", "-S")
    snat = [shlex.split(line) for line in nat.splitlines() if " -j SNAT " in line]
    expected = [["-A", "POSTROUTING", "-s", pool, "-o", "eth0", "-j", "SNAT", "--to-source", addr["upf"]]
                for pool in config["network"]["ue_pools"].values()]
    if [rule for rule in snat if rule[1] == "POSTROUTING"] != expected:
        raise ValueError("Unexpected UPF SNAT source scope")
    routes = inside("ext-dn", "ip", "-j", "route")
    parsed = json.loads(routes)
    for pool in config["network"]["ue_pools"].values():
        if not any(item.get("dst") == pool and item.get("gateway") == addr["upf"] for item in parsed):
            raise ValueError("Missing new UE pool return route")
    settings = inside("ims", "asterisk", "-rx", "sip show settings")
    if addr["ims"] + ":5060" not in settings:
        raise ValueError("IMS SIP socket does not match the isolated address")
    domain = "ims.mnc{}.mcc{}.3gppnetwork.org".format(config["radio"]["plmn"][3:].zfill(3), config["radio"]["plmn"][:3])
    if addr["ims"] not in inside("ext-dn", "getent", "hosts", domain):
        raise ValueError("Internal IMS DNS alias does not resolve")
    result = subprocess.run(["iperf3", "-c", addr["ext_dn"], "-B", addr["gnb"], "-b", "10M", "-t", "3", "-J"],
                            text=True, capture_output=True, timeout=15, check=True)
    speed = json.loads(result.stdout)
    if speed.get("error") or speed["end"]["sum_received"]["bytes"] == 0:
        raise ValueError("ext-DN bounded iperf check failed")
    return {"observed_at": datetime.now(timezone.utc).isoformat(),
            "services": {item["Service"]: item["Health"] for item in states},
            "snat_pools": list(config["network"]["ue_pools"].values()),
            "ims_address": addr["ims"], "internal_ims_dns": domain,
            "ext_dn_received_bits_per_second": speed["end"]["sum_received"]["bits_per_second"],
            "probe_path": "Spark bridge to ext-DN, limited to 10 Mbps for 3 seconds",
            "ue_pdu_verified": False, "ims_pdu_verified": False, "sip_registration_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(json.loads(args.config.read_text()), args.bundle.resolve())
    write_json(args.output, report)
    print(json.dumps(report))
