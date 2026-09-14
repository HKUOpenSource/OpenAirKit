#!/usr/bin/env python3
"""Collect a read-only Linux inventory; omit Docker environment and SIM material."""

import hashlib
import json
from pathlib import Path
import platform
import subprocess
from datetime import datetime, timezone


UNITS = ["oai-cn5g.service", "oai-gnb.service", "oai-ext-dn-iperf3.service",
         "oai-spark-collector.service", "oai-spark-web.service", "oai-console.service", "aoc-stack.target"]
IMAGES = ["oaisoftwarealliance/oai-" + nf + ":v2.2.1"
          for nf in ("nrf", "amf", "smf", "upf", "ausf", "udm", "udr")]
IMAGES += ["mysql:9.6", "oaisoftwarealliance/ims:latest", "oaisoftwarealliance/trf-gen-cn5g:latest"]


def command(argv, structured=False):
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30)
        return {"ok": result.returncode == 0, "returncode": result.returncode,
                "data": json.loads(result.stdout) if structured and result.returncode == 0 else result.stdout,
                "error": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"ok": False, "error": str(exc), "data": None}


def collect():
    result = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "host": platform.node(), "architecture": platform.machine()}
    result["usb_devices"] = []
    for device in Path("/sys/bus/usb/devices").glob("*"):
        if not (device / "idVendor").exists():
            continue
        item = {"sysfs": str(device)}
        for field in ("idVendor", "idProduct", "serial", "speed", "busnum", "devnum"):
            try:
                item[field] = (device / field).read_text().strip()
            except OSError:
                pass
        result["usb_devices"].append(item)
    for name, args, structured in [
        ("addresses", ["ip", "-j", "address", "show"], True),
        ("routes", ["ip", "-j", "-4", "route", "show", "table", "all"], True),
        ("routes_v6", ["ip", "-j", "-6", "route", "show", "table", "all"], True),
        ("rules", ["ip", "-j", "rule", "show"], True),
        ("listeners", ["ss", "-H", "-lntup"], False),
        ("sctp", ["ss", "-H", "-n", "-A", "sctp"], False),
        ("sudo", ["sudo", "-n", "true"], False),
        ("usb", ["lsusb"], False),
        ("usb_tree", ["lsusb", "-t"], False),
        ("cpu", ["lscpu", "-J"], True),
        ("memory", ["free", "-b"], False),
        ("disk", ["df", "-B1", str(Path.home())], False),
        ("units", ["systemctl", "show", *UNITS, "-p", "Id", "-p", "LoadState", "-p", "ActiveState",
                   "-p", "SubState", "-p", "MainPID", "-p", "NRestarts"], False),
    ]:
        result[name] = command(args, structured)
    networks = command(["docker", "network", "ls", "--format", "{{.ID}}"])
    ids = (networks.get("data") or "").split()
    result["networks"] = command(["docker", "network", "inspect", *ids], True) if ids else networks
    result["images"] = {}
    for ref in IMAGES:
        inspected = command(["docker", "image", "inspect", ref], True)
        if inspected["ok"]:
            item = inspected["data"][0]
            result["images"][ref] = {key: item.get(key) for key in ("Id", "RepoDigests", "Architecture", "Os")}
        else:
            result["images"][ref] = {"error": "Image inspect failed"}
    result["file_hashes"] = {}
    for path in [Path.home() / ".local/bin/oai-spark-services.sh",
                 Path.home() / "oai-only-cn5g/docker-compose.yaml",
                 Path.home() / "oai-only-cn5g/docker-compose.yml",
                 Path.home() / "oai-only-cn5g/conf/config.yaml",
                 Path("/etc/systemd/system/oai-gnb.service"),
                 Path("/usr/local/libexec/oai-ext-dn-iperf3-server")]:
        try:
            result["file_hashes"][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            result["file_hashes"][str(path)] = {"error": str(exc)}
    return result


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
