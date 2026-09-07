#!/usr/bin/env python3
"""Offline isolation checks for the deployment plan; never changes host state."""

import argparse
import ipaddress
import json
from pathlib import Path, PurePosixPath
import sys


ROOT = Path(__file__).resolve().parents[1]


def endpoints_overlap(left, right):
    if (left["protocol"], left["port"]) != (right["protocol"], right["port"]):
        return False
    a = ipaddress.ip_address(left["address"])
    b = ipaddress.ip_address(right["address"])
    # Treat IPv6 wildcard binds conservatively: they may also accept IPv4.
    return a == b or a.is_unspecified or b.is_unspecified


def validate(config):
    errors = []
    try:
        _validate(config, errors)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append("Malformed configuration: {}".format(exc))
    return errors


def _validate(config, errors):
    if config["schema_version"] != 1:
        errors.append("Unsupported schema_version")
    legacy = config["legacy"]
    names = config["names"]
    for key in ("compose_project", "docker_network", "bridge", "systemd_target"):
        value = names[key]
        if not value.startswith("aoc-") or value in legacy["reserved_names"]:
            errors.append("{} must use an independent aoc- name".format(key))
    if len(names["bridge"].encode("utf-8")) > 15:
        errors.append("Linux bridge name exceeds 15 bytes")
    if names["systemd_target"] != "aoc-stack.target":
        errors.append("systemd_target differs from the supplied templates")
    if legacy["radio_unit"] != "oai-gnb.service":
        errors.append("Legacy radio unit differs from the switching contract")

    for key, base in {"install": "/opt", "config": "/etc", "state": "/var/lib",
                      "run": "/run", "logs": "/var/log"}.items():
        path = PurePosixPath(config["paths"][key])
        root = PurePosixPath(base) / "agentic-ocudu"
        if ".." in path.parts or (path != root and root not in path.parents):
            errors.append("{} must stay under {}".format(key, root))

    subnet = ipaddress.IPv4Network(config["network"]["subnet"])
    networks = [("core", subnet)] + [
        (name, ipaddress.IPv4Network(value))
        for name, value in config["network"]["ue_pools"].items()
    ]
    if not config["network"]["ue_pools"]:
        errors.append("At least one UE address pool is required")
    reserved = [ipaddress.IPv4Network(value) for value in legacy["reserved_subnets"]]
    for index, (name, network) in enumerate(networks):
        if not network.is_private or network.is_loopback or network.is_link_local:
            errors.append("{} must use a private routable subnet".format(name))
        for other in reserved + [item[1] for item in networks[:index]]:
            if network.overlaps(other):
                errors.append("{} {} overlaps {}".format(name, network, other))

    addresses = config["network"]["addresses"]
    used = set()
    for name, value in addresses.items():
        addr = ipaddress.IPv4Address(value)
        if addr not in subnet or addr in (subnet.network_address, subnet.broadcast_address):
            errors.append("{} is not a usable core address".format(name))
        if addr in used:
            errors.append("Duplicate core address: {}".format(addr))
        used.add(addr)

    listeners = config["listeners"]
    by_name = {}
    for index, endpoint in enumerate(listeners):
        name = endpoint["name"]
        if name in by_name:
            errors.append("Duplicate listener name: {}".format(name))
        by_name[name] = endpoint
        address = ipaddress.IPv4Address(endpoint["address"])
        if address.is_unspecified:
            errors.append("{} must not bind a wildcard address".format(name))
        elif address not in used and not address.is_loopback:
            errors.append("{} binds an unallocated address".format(name))
        protocol, port = endpoint["protocol"], endpoint["port"]
        if protocol not in ("tcp", "udp", "sctp"):
            errors.append("Unsupported protocol: {}".format(protocol))
        if type(port) is not int or not 1 <= port <= 65535:
            errors.append("Invalid port for {}".format(name))
        if port in legacy.get("reserved_{}_ports".format(protocol), []):
            errors.append("{} uses a reserved {} port {}".format(name, protocol, port))
        for other in legacy["listeners"] + listeners[:index]:
            if endpoints_overlap(endpoint, other):
                errors.append("{} conflicts with {}".format(name, other["name"]))

    expected = {
        "amf_n2": (addresses["amf"], "sctp", 38412),
        "gnb_n3": (addresses["gnb"], "udp", 2152),
        "upf_n3": (addresses["upf"], "udp", 2152),
        "upf_n4": (addresses["upf"], "udp", 8805),
    }
    for name, binding in expected.items():
        actual = by_name[name]
        if (actual["address"], actual["protocol"], actual["port"]) != binding:
            errors.append("{} disagrees with the core address/protocol plan".format(name))
    for name in ("monitor_web", "ocudu_control"):
        endpoint = by_name[name]
        if endpoint["address"] != "127.0.0.1" or endpoint["protocol"] != "tcp":
            errors.append("{} must use loopback TCP".format(name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/spark.example.json")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    errors = validate(config)
    if errors:
        for error in errors:
            print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    print("Offline isolation checks passed. No host state was inspected or changed.")
    print("Scaffold only: build, images, RF configuration and switching remain unverified.")
    if args.plan:
        print("\nCompose: {} | bridge: {} | subnet: {}".format(
            config["names"]["compose_project"], config["names"]["bridge"],
            config["network"]["subnet"]))
        for endpoint in config["listeners"]:
            print("  {name:16} {address}:{port}/{protocol}".format(**endpoint))
        print("\nTarget after implementation: {}".format(config["names"]["systemd_target"]))
        print("Legacy return entry: {} start".format(config["legacy"]["start_script"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
