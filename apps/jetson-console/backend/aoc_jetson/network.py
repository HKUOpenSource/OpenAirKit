"""Bound data-path operations and a journaled, fixed-parameter network helper."""
import json
import ipaddress
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from .hardware import discover


KINDS = frozenset({"gateway", "upf", "ext_dn", "public"})
ACTIONS = frozenset({"prepare", "promote", "fallback", "restore"})
HELPER_ENTRY = "/opt/agentic-ocudu/jetson/current/deploy/network_entry.py"


def run(argv, timeout=10, cancel=None, tick=None, check=True):
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          start_new_session=True) as process:
        deadline = time.monotonic() + timeout
        while True:
            try:
                stdout, stderr = process.communicate(timeout=.2)
                result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
                if check and result.returncode:
                    raise RuntimeError((stderr.strip() or stdout.strip() or "command failed")[:350])
                return stdout if check else result
            except subprocess.TimeoutExpired:
                if tick:
                    tick()
                if time.monotonic() > deadline or cancel is not None and cancel.is_set():
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                    raise TimeoutError("Operation cancelled" if cancel is not None and cancel.is_set()
                                       else "Command timed out")


def ip_json(*args):
    value = json.loads(run(["ip", "-j", *args]))
    if not isinstance(value, list):
        raise RuntimeError("Unexpected iproute2 JSON response")
    return value


def global_addresses(interface):
    return [entry["local"] for item in ip_json("-4", "address", "show", "dev", interface)
            for entry in item.get("addr_info", []) if entry.get("scope") == "global"]


def route_to(address, source=None):
    args = ["-4", "route", "get", address]
    if source:
        args += ["from", source]
    routes = ip_json(*args)
    if len(routes) != 1:
        raise ValueError("A unique route was not found")
    return routes[0]


def inspect(config):
    found = discover(config)
    data_interface = found["data_interface"]
    data_addresses = global_addresses(data_interface)
    if len(data_addresses) != 1 or ipaddress.ip_address(data_addresses[0]) not in ipaddress.ip_network("192.168.224.0/22"):
        raise ValueError("A unique RNDIS DHCP address was not found")
    configured_wifi = config["management"]["wifi_interface"]
    if configured_wifi == "auto":
        candidates = sorted(path.name for path in Path("/sys/class/net").iterdir()
                            if (path / "wireless").exists())
        if len(candidates) != 1:
            raise ValueError("A unique management Wi-Fi interface was not found")
        wifi = candidates[0]
    else:
        wifi = configured_wifi
    wifi_addresses = global_addresses(wifi)
    if len(wifi_addresses) != 1:
        raise ValueError("A unique management Wi-Fi address was not found")
    tailscale = config["management"]["tailscale_interface"]
    if route_to(config["management"]["spark_address"]).get("dev") != tailscale:
        raise ValueError("Spark management route is not protected by Tailscale")
    return {"data_interface": data_interface, "data_address": data_addresses[0],
            "wifi_interface": wifi, "wifi_address": wifi_addresses[0],
            "tailscale_interface": tailscale}


def targets(config):
    plane = config["network"]["user_plane"]
    return {"gateway": plane["rndis_gateway"], "upf": plane["upf_probe"],
            "ext_dn": plane["ext_dn"], "public": plane["public_probe"]}


class Network:
    def __init__(self, config, config_path):
        self.config = config
        self.config_path = str(config_path)
        self.previous = None

    def action(self, action, cancel=None):
        if action not in ACTIONS:
            raise ValueError("Network action is not allow-listed")
        import sys
        result = run([sys.executable, "-I", HELPER_ENTRY, "--config", self.config_path,
                      "--action", action], timeout=50, cancel=cancel, check=False)
        try:
            reply = json.loads(result.stdout)
        except ValueError:
            detail = (result.stderr.strip() or "Invalid helper response").splitlines()[-1][-350:]
            raise RuntimeError("Network " + action + ": " + detail) from None
        if result.returncode or not isinstance(reply, dict) or reply.get("ok") is not True:
            detail = reply.get("error", {}) if isinstance(reply, dict) else {}
            raise RuntimeError("Network " + action + ": " + str(detail.get("message", "Helper failed"))[:350])
        return reply["result"]

    def snapshot(self):
        at = time.time()
        try:
            state = inspect(self.config)
            interface = state["data_interface"]
            counters = [int((Path("/sys/class/net") / interface / "statistics" / name).read_text())
                        for name in ("rx_bytes", "tx_bytes")]
            rates = [None, None]
            if self.previous:
                previous_at, previous = self.previous
                if at > previous_at and all(new >= old for new, old in zip(counters, previous)):
                    rates = [(new - old) * 8 / (at - previous_at) for new, old in zip(counters, previous)]
            self.previous = (at, counters)
            public_route = route_to(targets(self.config)["public"], state["data_address"])
            return {"at": at, "quality": "ok", **state, "ipv4_egress": public_route.get("dev"),
                    "rx_bps": rates[0], "tx_bps": rates[1],
                    "ipv6": {"quality": "unavailable", "reason": "IPv6 data path is not verified"}}
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            return {"at": at, "quality": "unavailable", "reason": str(error)[:300],
                    "rx_bps": None, "tx_bps": None,
                    "ipv6": {"quality": "unavailable", "reason": "IPv6 data path is not verified"}}

    def probe(self, kind, cancel=None):
        if kind not in KINDS:
            raise ValueError("Probe kind is not allow-listed")
        state = inspect(self.config)
        target = targets(self.config)[kind]
        path = route_to(target, state["data_address"])
        if path.get("dev") != state["data_interface"]:
            raise ValueError("Probe route is not bound to the RM520N data interface")
        try:
            output = run(["ping", "-4", "-n", "-I", state["data_interface"], "-c", "2", "-W", "2", target],
                         timeout=6, cancel=cancel)
            loss = re.search(r"([\d.]+)% packet loss", output)
            timing = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", output)
            return {"at": time.time(), "kind": kind, "state": "ok",
                    "interface": state["data_interface"], "source": state["data_address"],
                    "latency_ms": float(timing[2]) if timing else None,
                    "jitter_ms": float(timing[4]) if timing else None,
                    "loss_pct": float(loss[1]) if loss else None}
        except RuntimeError:
            return {"at": time.time(), "kind": kind, "state": "failed",
                    "interface": state["data_interface"], "source": state["data_address"],
                    "reason": "No valid ICMP reply; PDU release is not inferred"}

    def speed(self, direction, duration, parallel, cancel, on_sample):
        if direction not in {"download", "upload"} or type(duration) is not int or not 5 <= duration <= 30 \
                or type(parallel) is not int or not 1 <= parallel <= 4:
            raise ValueError("Invalid fixed speed-test parameters")
        state = inspect(self.config)
        target = targets(self.config)["ext_dn"]
        if route_to(target, state["data_address"]).get("dev") != state["data_interface"]:
            raise ValueError("Speed-test route is not bound to the RM520N data interface")
        plane = self.config["network"]["user_plane"]
        argv = ["iperf3", "-4", "-c", target, "-p", str(plane["iperf_port"]),
                "-B", state["data_address"], "-t", str(duration), "-P", str(parallel), "-J"]
        if direction == "download":
            argv.append("-R")
        started = time.time()
        counter = Path("/sys/class/net") / state["data_interface"] / "statistics" / (
            "rx_bytes" if direction == "download" else "tx_bytes")
        previous = [time.monotonic(), int(counter.read_text())]

        def tick():
            current = time.monotonic()
            if current - previous[0] < 1:
                return
            if route_to(target, state["data_address"]).get("dev") != state["data_interface"]:
                raise ValueError("Route changed during speed test")
            count = int(counter.read_text())
            rate = (count - previous[1]) * 8 / (current - previous[0]) if count >= previous[1] else None
            on_sample({"at": time.time(), "bps": rate, "elapsed": time.time() - started, "final": False})
            previous[:] = [current, count]

        output = run(argv, timeout=duration + 20, cancel=cancel, tick=tick)
        if route_to(target, state["data_address"]).get("dev") != state["data_interface"]:
            raise ValueError("Final route is not bound to the RM520N data interface")
        value = json.loads(output)
        if value.get("error"):
            raise ValueError(str(value["error"])[:250])
        received = value.get("end", {}).get("sum_received", {})
        bps = received.get("bits_per_second")
        if not isinstance(bps, (int, float)) or not 0 < bps < 1e12 or received.get("bytes", 0) <= 0:
            raise ValueError("No valid receiver throughput")
        return {"bps": bps, "bytes": received["bytes"], "receiver_verified": True,
                "interface": state["data_interface"], "source": state["data_address"]}


def helper(config, action):
    if os.geteuid() != 0 or not config.get("commissioned") or not config.get("management_verified"):
        raise ValueError("Commissioning, management verification and root execution are required")
    if action not in ACTIONS:
        raise ValueError("Network action is not allow-listed")
    state = inspect(config)
    journal = Path(config["state_dir"]) / "network-state.json"
    owned = json.loads(journal.read_text()) if journal.exists() else {"routes": []}
    if action == "restore":
        for route in reversed(owned["routes"]):
            current = ip_json("-4", "route", "show", route["destination"])
            ours = [item for item in current if str(item.get("protocol")) == "186"
                    and item.get("dev") == route["interface"]]
            if current and not ours:
                raise ValueError("An owned route changed; manual inspection is required")
            if ours:
                run(["ip", "route", "del", route["destination"], "dev", route["interface"], "proto", "186"])
        journal.unlink(missing_ok=True)
        return {"restored": True}
    if action == "prepare":
        for kind in ("upf", "ext_dn", "public"):
            target = targets(config)[kind]
            route = route_to(target, state["data_address"])
            if route.get("dev") != state["data_interface"]:
                raise ValueError(kind + " route is not bound to the RM520N data interface")
        journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not journal.exists():
            fd = os.open(journal, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(owned, output)
        return {"prepared": True, "mode": "existing_networkmanager_routes",
                "management_protected": True, "mutations": 0}
    defaults = ip_json("-4", "route", "show", "default")
    data_default = any(item.get("dev") == state["data_interface"] for item in defaults)
    wifi_default = any(item.get("dev") == state["wifi_interface"] for item in defaults)
    if action == "promote" and data_default and wifi_default:
        return {"mode": "5g", "management_protected": True,
                "owner": "existing_networkmanager_routes", "mutations": 0}
    if action == "fallback" and wifi_default:
        return {"mode": "wifi-available", "management_protected": True,
                "reason": "The platform does not delete an unowned RNDIS default route", "mutations": 0}
    raise ValueError("Required default-route evidence is unavailable")


def main():
    import argparse
    from .config import load
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--action", choices=sorted(ACTIONS), required=True)
    args = parser.parse_args()
    try:
        result = helper(load(args.config), args.action)
        print(json.dumps({"ok": True, "result": result}))
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "action": args.action,
                          "error": {"type": type(error).__name__, "message": str(error)[:350]}}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
