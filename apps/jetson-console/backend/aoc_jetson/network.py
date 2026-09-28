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
    wifi_defaults = [row for row in defaults if row.get("dev") == wifi
                     and row.get("gateway") and not row.get("nexthops")]
    gateways = {row["gateway"] for row in wifi_defaults}
    if len(gateways) != 1:
        raise ValueError("A unique Wi-Fi fallback gateway is required")
    return {"wifi_interface": wifi, "wifi_address": wifi_addresses[0],
            "wifi_gateway": gateways.pop(),
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
                # The diagnostic target has a dedicated modem route. It must
                # not stand in for the default path used by ordinary traffic.
                public_route = route_to("1.1.1.1")
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


def managed_defaults(config, action):
    """Own only protocol-186 defaults at metrics 5 (Wi-Fi) and 10 (cellular).

    Main-table routes work on the deployed Jetson kernels without policy routing.
    NetworkManager profiles, its defaults and Tailscale routes are never edited.
    The Wi-Fi path stays available, but tunnel transport can reconnect on switch.
    """
    directory = Path(config["state_dir"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    journal = directory / "egress-state.json"
    fd = os.open(directory / "egress.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if journal.is_symlink():
            raise ValueError("Unsafe egress journal")
        owned = json.loads(journal.read_text())["routes"] if journal.exists() else []
        if not isinstance(owned, list):
            raise ValueError("Invalid egress journal")

        def rows():
            return ip_json("-N", "-4", "route", "show", "default")

        def matches(row, record):
            return (row.get("dst") == "default" and row.get("dev") == record["interface"]
                    and row.get("gateway") == record["gateway"]
                    and row.get("metric", 0) == record["metric"]
                    and str(row.get("protocol")) == "186" and not row.get("nexthops")
                    and row.get("type", "unicast") == "unicast")

        seen = set()
        current = rows()
        for record in owned:
            if (not isinstance(record, dict) or set(record) != {"interface", "gateway", "metric", "pending"}
                    or record["metric"] not in (5, 10) or record["metric"] in seen
                    or type(record["pending"]) is not bool
                    or not isinstance(record["interface"], str)
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", record["interface"])):
                raise ValueError("Invalid egress ownership record")
            ipaddress.IPv4Address(record["gateway"])
            seen.add(record["metric"])
            if record["pending"]:
                raise ValueError("Uncertain egress operation; inspect before continuing")
            same = [row for row in current if row.get("metric", 0) == record["metric"]]
            if same and (len(same) != 1 or not matches(same[0], record)):
                raise ValueError("An owned default route changed; inspect before continuing")
        for row in current:
            if (row.get("metric", 0) in (5, 10) or str(row.get("protocol")) == "186") \
                    and not any(matches(row, record) for record in owned):
                raise ValueError("Reserved egress route conflicts with another owner")

        mutations = 0

        def remove(record):
            nonlocal mutations
            present = [row for row in rows() if row.get("metric", 0) == record["metric"]]
            if present:
                if len(present) != 1 or not matches(present[0], record):
                    raise ValueError("An owned default route changed")
                run(["ip", "-4", "route", "del", "default", "via", record["gateway"],
                     "dev", record["interface"], "metric", str(record["metric"]), "proto", "186"])
                mutations += 1
            if any(matches(row, record) for row in rows()):
                raise ValueError("Owned default route remains after removal")
            owned.remove(record)
            save_routes(journal, owned)

        def add(interface, gateway, metric):
            nonlocal mutations
            record = {"interface": interface, "gateway": gateway, "metric": metric, "pending": False}
            prior = next((r for r in owned if r["metric"] == metric), None)
            if prior == record and any(matches(row, record) for row in rows()):
                return
            if prior:
                remove(prior)
            if any(row.get("metric", 0) == metric for row in rows()):
                raise ValueError("Reserved default metric is occupied")
            record["pending"] = True
            owned.append(record)
            save_routes(journal, owned)
            try:
                run(["ip", "-4", "route", "add", "default", "via", gateway,
                     "dev", interface, "metric", str(metric), "proto", "186"])
            except RuntimeError:
                # A definite rejection is different from a timeout with an
                # unknown outcome. The latter keeps its pending journal.
                owned.remove(record)
                save_routes(journal, owned)
                raise
            mutations += 1
            if not any(matches(row, record) for row in rows()):
                raise ValueError("New default route failed readback")
            record["pending"] = False
            save_routes(journal, owned)

        if action == "restore":
            for record in list(owned):
                remove(record)
            journal.unlink(missing_ok=True)
            return {"restored": True, "mutations": mutations}

        state = inspect_management(config)
        wifi, gateway = state["wifi_interface"], state["wifi_gateway"]
        ipaddress.IPv4Address(gateway)
        if any(row.get("metric", 0) <= 10 and not any(matches(row, r) for r in owned)
               for row in current):
            raise ValueError("A foreign high-priority default prevents managed failover")
        if action == "promote":
            data = inspect(config)
            interface = data["data_interface"]
            cell_gateway = targets(config)["gateway"]
            if route_to(cell_gateway).get("dev") != interface:
                raise ValueError("Modem gateway route is unavailable")
            prior = next((r for r in owned if r["metric"] == 10), None)
            if prior and (prior["interface"] != interface or prior["gateway"] != cell_gateway):
                # Preserve a usable fallback while replacing an enumerated modem.
                add(wifi, gateway, 5)
            add(interface, cell_gateway, 10)
            for record in list(owned):
                if record["metric"] == 5:
                    remove(record)
            mode = "cellular"
        else:
            add(wifi, gateway, 5)
            for record in list(owned):
                if record["metric"] == 10:
                    remove(record)
            interface, mode = wifi, "wifi"
        actual = route_to("1.1.1.1").get("dev")
        if actual != interface:
            raise ValueError("Ordinary IPv4 route did not select the requested interface")
        return {"mode": mode, "ipv4_egress": actual, "management_protected": True,
                "mutations": mutations}


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
                # USB re-enumeration can change the interface name. Retire only
                # the exact journaled route (or its already removed kernel entry).
                current = route_rows(destination)
                if current:
                    run(["ip", "-4", "route", "del", destination, "via", prior["gateway"],
                         "dev", prior["interface"], "proto", "186"])
                owned.remove(prior)
                save_routes(journal, owned)
            path = route_to(address, state["data_address"])
            if path.get("dev") == config["management"]["tailscale_interface"]:
                raise ValueError("Data target conflicts with a management tunnel route")
            bound = path.get("dev") == interface
            existing = route_rows(destination)
            if bound and existing:
                continue
            if existing:
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
        return managed_defaults(config, "fallback")
    if action == "restore":
        managed_defaults(config, "restore")
        return managed_routes(config, "restore")
    if action == "prepare":
        if not (Path(config["state_dir"]) / "egress-state.json").exists():
            managed_defaults(config, "fallback")
        return managed_routes(config, "prepare")
    if action == "promote":
        managed_routes(config, "prepare")
    return managed_defaults(config, action)


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
