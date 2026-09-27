"""Bound data-path operations and a journaled, fixed-parameter network helper."""
import json
import ipaddress
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from .hardware import discover


KINDS = frozenset({"gateway", "upf", "ext_dn", "public"})
ACTIONS = frozenset({"protect", "prepare", "promote", "fallback", "restore"})
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


def inspect(config, require_management=True):
    found = discover(config)
    data_interface = found["data_interface"]
    data_addresses = global_addresses(data_interface)
    if len(data_addresses) != 1 or ipaddress.ip_address(data_addresses[0]) not in ipaddress.ip_network("192.168.224.0/22"):
        raise ValueError("A unique RNDIS DHCP address was not found")
    state = {"data_interface": data_interface, "data_address": data_addresses[0]}
    if not require_management:
        try:
            protected = {**state, **inspect_management(config)}
            return {**protected, "management_protected": True}
        except (OSError, ValueError, RuntimeError) as error:
            return {**state, "management_protected": False, "management_reason": str(error)[:240]}
    return {**state, **inspect_management(config)}


def inspect_management(config):
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
    defaults = ip_json("-4", "route", "show", "default")
    if not defaults:
        raise ValueError("Management Wi-Fi needs a default route")
    metric = min(row.get("metric", 0) for row in defaults)
    if any(row.get("dev") != wifi or row.get("nexthops") for row in defaults
           if row.get("metric", 0) == metric):
        raise ValueError("Management Wi-Fi must be the preferred IPv4 default; review NetworkManager settings")
    return {"wifi_interface": wifi, "wifi_address": wifi_addresses[0],
            "tailscale_interface": tailscale, "management_protected": True}


def targets(config):
    plane = config["diagnostics"]
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
            state = inspect(self.config, require_management=False)
            interface = state["data_interface"]
            device = Path("/sys/class/net") / interface
            ifindex = int((device / "ifindex").read_text())
            counters = [int((device / "statistics" / name).read_text())
                        for name in ("rx_bytes", "tx_bytes")]
            if int((device / "ifindex").read_text()) != ifindex:
                raise ValueError("Data interface changed while sampling counters")
            identity = (interface, ifindex)
            sampled_at = time.monotonic()
            rates = [None, None]
            if self.previous:
                previous_identity, previous_at, previous = self.previous
                if (identity == previous_identity and sampled_at > previous_at
                        and all(new >= old for new, old in zip(counters, previous))):
                    rates = [(new - old) * 8 / (sampled_at - previous_at)
                             for new, old in zip(counters, previous)]
            # Renames, replacements and counter resets start a fresh interval.
            self.previous = (identity, sampled_at, counters)
            try:
                public_route = route_to(targets(self.config)["public"], state["data_address"])
            except (OSError, ValueError, RuntimeError):
                public_route = {}
            return {"at": at, "quality": "ok", **state, "ipv4_egress": public_route.get("dev"),
                    "rx_bps": rates[0], "tx_bps": rates[1],
                    "ipv6": {"quality": "unavailable", "reason": "IPv6 data path is not verified"}}
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            self.previous = None
            try:
                management = inspect_management(self.config)
            except (OSError, ValueError, RuntimeError) as guard:
                management = {"management_protected": False, "management_reason": str(guard)[:240]}
            return {"at": at, "quality": "unavailable", **management, "reason": str(error)[:300],
                    "rx_bps": None, "tx_bps": None,
                    "ipv6": {"quality": "unavailable", "reason": "IPv6 data path is not verified"}}

    def probe(self, kind, cancel=None):
        if kind not in KINDS:
            raise ValueError("Probe kind is not allow-listed")
        state = inspect(self.config, require_management=False)
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


def route_rows(destination):
    # Protocol 186 otherwise appears as its iproute2 name, "bgp".
    return ip_json("-N", "-4", "route", "show", "table", "main", "exact", destination)


def matches_route(row, record):
    return (row.get("dst") in (record["destination"], record["destination"].removesuffix("/32"))
            and str(row.get("protocol")) == "186" and row.get("dev") == record["interface"]
            and row.get("gateway") == record["gateway"] and row.get("metric", 0) == 0
            and row.get("type", "unicast") == "unicast" and not row.get("nexthops"))


def save_routes(journal, routes):
    temporary = journal.with_name(".network-state-" + str(time.time_ns()))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump({"routes": routes}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, journal)
        directory = os.open(journal.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def managed_routes(config, action):
    """Serialize exact host-route ownership; never replace another owner's route."""
    directory = Path(config["state_dir"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    journal = directory / "network-state.json"
    fd = os.open(directory / "network.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if journal.is_symlink():
            raise ValueError("Unsafe route journal")
        owned = json.loads(journal.read_text())["routes"] if journal.exists() else []
        destinations = {targets(config)[kind] + "/32" for kind in ("upf", "ext_dn", "public")}
        if not isinstance(owned, list):
            raise ValueError("Invalid route journal")
        seen = set()
        for record in owned:
            if (not isinstance(record, dict) or record.get("destination") not in destinations
                    or record.get("destination") in seen
                    or record.get("gateway") != targets(config)["gateway"]
                    or not isinstance(record.get("interface"), str)
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", record["interface"])
                    or not isinstance(record.get("pending"), bool)):
                raise ValueError("Invalid route ownership record; inspect before continuing")
            seen.add(record["destination"])
            current = route_rows(record["destination"])
            if current and (record["pending"] or len(current) != 1 or not matches_route(current[0], record)):
                raise ValueError("An owned route changed or has an uncertain outcome; inspect before continuing")
        if action == "restore":
            # Cleanup still works after the modem, DHCP address or Wi-Fi disappears.
            for record in list(reversed(owned)):
                current = route_rows(record["destination"])
                if current:
                    if record["pending"] or len(current) != 1 or not matches_route(current[0], record):
                        raise ValueError("An owned route changed; refusing to delete it")
                    run(["ip", "-4", "route", "del", record["destination"], "via", record["gateway"],
                         "dev", record["interface"], "proto", "186"])
                owned.remove(record)
                save_routes(journal, owned)
            journal.unlink(missing_ok=True)
            return {"restored": True}

        state = inspect(config)
        interface = state["data_interface"]
        gateway = targets(config)["gateway"]
        if route_to(gateway).get("dev") != interface:
            raise ValueError("Modem gateway is not reachable on the discovered data interface")
        additions = []
        for destination in sorted(destinations):
            address = destination.removesuffix("/32")
            if address in (state.get("wifi_address"), config["management"]["spark_address"]):
                raise ValueError("Data target conflicts with a management address")
            prior = next((r for r in owned if r["destination"] == destination), None)
            if prior and prior["interface"] != interface:
                raise ValueError("Modem interface changed; stop to clean up old routes first")
            path = route_to(address, state["data_address"])
            if path.get("dev") == config["management"]["tailscale_interface"]:
                raise ValueError("Data target conflicts with a management tunnel route")
            bound = path.get("dev") == interface
            if bound:
                continue
            if route_rows(destination):
                raise ValueError("Conflicting data host route; no existing route will be replaced")
            additions.append({"destination": destination, "gateway": gateway,
                              "interface": interface, "pending": True})
        for record in additions:
            owned = [r for r in owned if r["destination"] != record["destination"]] + [record]
            save_routes(journal, owned)  # Record intent before any network mutation.
            try:
                run(["ip", "-4", "route", "add", record["destination"], "via", gateway,
                     "dev", interface, "proto", "186"])
            except RuntimeError:
                # A definite command rejection must not claim a competing route.
                owned.remove(record)
                save_routes(journal, owned)
                raise
            current = route_rows(record["destination"])
            if len(current) != 1 or not matches_route(current[0], record):
                raise ValueError("New route readback failed; ownership remains uncertain")
            record["pending"] = False
            save_routes(journal, owned)
        for destination in destinations:
            if route_to(destination.removesuffix("/32"), state["data_address"]).get("dev") != interface:
                raise ValueError("Data route verification failed; inspect policy routing")
        return {"prepared": True, "mode": "bound_data_routes", "management_protected": True,
                "mutations": len(additions), "owned_routes": len(owned)}


def helper(config, action):
    if os.geteuid() != 0 or not config.get("commissioned") or not config.get("management_verified"):
        raise ValueError("Commissioning, management verification and root execution are required")
    if action not in ACTIONS:
        raise ValueError("Network action is not allow-listed")
    if action == "protect":
        inspect_management(config)
        return {"management_protected": True, "mutations": 0}
    if action in {"prepare", "restore", "promote"}:
        return managed_routes(config, "prepare" if action == "promote" else action)
    state = inspect(config)
    defaults = ip_json("-4", "route", "show", "default")
    wifi_default = any(item.get("dev") == state["wifi_interface"] for item in defaults)
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
