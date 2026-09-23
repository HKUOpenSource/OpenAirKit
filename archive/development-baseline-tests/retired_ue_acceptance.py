#!/usr/bin/env python3
"""Temporary, explicit Jetson acceptance commands; no daemon or automatic recovery."""

import argparse
from contextlib import contextmanager
import csv
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import pwd
import re
import sqlite3
import subprocess
import time

STATE = Path("/var/lib/agentic-ocudu-ue")
DB = Path("/var/lib/oai-console/console.db")
PORT = Path("/dev/serial/by-id/usb-Quectel_RM520N-GL_e666bdd0-if02-port0")
SYS_NET = Path("/sys/class/net")
SYS_TTY = Path("/sys/class/tty")
GATEWAY = "192.168.225.1"
DIRECTION_SETTLE_SECONDS = 3
PROFILES = {"legacy": {"data": "10.0.0.0/24", "ims": "10.0.9.0/24", "target": "192.168.70.135", "ims_type": "IPV4V6"},
            "ocudu": {"data": "10.80.0.0/24", "ims": "10.80.9.0/24", "target": "172.28.80.15", "ims_type": "IP"}}
QUERIES = ("AT", "ATI", "AT+CGMR", "AT+CIMI", "AT+CPIN?", "AT+CFUN?", "AT+COPS?",
           "AT+CEREG?", "AT+C5GREG?", 'AT+QENG="servingcell"', "AT+CGDCONT?", "AT+CGACT?",
           'AT+QMAP="MPDN_rule"', 'AT+QMAP="MPDN_status"', 'AT+QCFG="usbnet"')


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, timeout=kwargs.pop("timeout", 45),
                          capture_output=True, text=True, **kwargs).stdout


def save(name, value):
    path = STATE / name
    if path.is_symlink():
        raise ValueError("Private state cannot be a symlink")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


@contextmanager
def console_db():
    account = pwd.getpwnam("oai-console")
    os.setegid(account.pw_gid)
    os.seteuid(account.pw_uid)
    try:
        connection = sqlite3.connect(DB, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()
    finally:
        os.seteuid(0)
        os.setegid(0)


def idle(connection):
    operation = connection.execute("SELECT kind FROM operation_lock WHERE slot=1").fetchone()
    if operation and operation[0] != "maintenance":
        raise ValueError("Original console has an active operation; finish/cancel it first")
    for table in ("jobs", "speed_tests"):
        if connection.execute("SELECT 1 FROM " + table + " WHERE state IN ('queued','running','cancelling') LIMIT 1").fetchone():
            raise ValueError("Original console has an unfinished task: " + table)


def maintenance_required():
    with console_db() as connection:
        idle(connection)
        setting = connection.execute("SELECT value FROM settings WHERE key='maintenance_mode'").fetchone()
        operation = connection.execute("SELECT kind FROM operation_lock WHERE slot=1").fetchone()
        if not setting or json.loads(setting[0]) is not True or operation != ("maintenance",):
            raise ValueError("Original platform must hold the maintenance lock")


def set_mode(value):
    with console_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        idle(connection)
        if value is None:
            connection.execute("DELETE FROM settings WHERE key='maintenance_mode'")
        else:
            connection.execute("INSERT INTO settings(key,value,updated_at) VALUES('maintenance_mode',?,?) "
                               "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                               (value, time.time()))
        connection.execute("DELETE FROM operation_lock WHERE slot=1 AND kind='maintenance'")
        if value is not None and json.loads(value) is True:
            connection.execute("INSERT INTO operation_lock(slot,kind,operation_id,acquired_at) VALUES(1,'maintenance','serial-port',?)",
                               (time.time(),))


def stop_console():
    maintenance_required()
    print("UE: stopping original console and releasing its serial port", flush=True)
    run(["systemctl", "stop", "--no-block", "oai-console.service"], timeout=10)
    for attempt in range(30):
        state = run(["systemctl", "show", "oai-console.service", "-p", "ActiveState", "--value"], timeout=5).strip()
        if state in ("inactive", "failed"):
            return
        if attempt == 15:
            maintenance_required()
            process = run(["systemctl", "show", "oai-console.service", "-p", "ExecStart", "--value"], timeout=5)
            if "oai_console.main:app" not in process or "/opt/oai-console/venv/bin/python" not in process:
                raise ValueError("Original console executable changed; refusing an additional exit signal")
            print("UE: no business tasks active; closing residual original Web connections with SIGINT", flush=True)
            run(["systemctl", "kill", "--kill-who=main", "--signal=SIGINT", "oai-console.service"], timeout=10)
        time.sleep(1)
    raise TimeoutError("Original console has not released its process; no AT access attempted")


class Modem:
    def __init__(self, check_identity=True, allow_minimum=False):
        self.check_identity = check_identity
        self.allow_minimum = allow_minimum
        self.identity_pending = False

    def __enter__(self):
        import serial
        maintenance_required()
        if PORT.resolve() != Path("/dev/ttyUSB2"):
            raise ValueError("AT port mapping changed; inspect hardware before continuing")
        occupied = subprocess.run(["fuser", str(PORT.resolve())], capture_output=True, text=True)
        if occupied.returncode != 1 or occupied.stdout.strip() or occupied.stderr.strip():
            raise ValueError("AT port is occupied or ownership check failed")
        self.serial = serial.Serial(str(PORT), 115200, timeout=0.2, write_timeout=2, exclusive=True)
        try:
            self.query("AT")
            baseline = STATE / "baseline.json"
            if baseline.exists() and self.check_identity:
                if self.allow_minimum and "+CFUN: 0" in self.query("AT+CFUN?"):
                    self.identity_pending = True
                else:
                    self.verify_identity()
        except BaseException:
            self.serial.close()
            raise
        return self

    def __exit__(self, *args):
        self.serial.close()

    def verify_identity(self):
        original = json.loads((STATE / "baseline.json").read_text())["responses"]["AT+CIMI"]
        expected = [line for line in original if re.fullmatch(r"[0-9]{15}", line)]
        actual = [line for line in self.query("AT+CIMI") if re.fullmatch(r"[0-9]{15}", line)]
        if len(expected) != 1 or actual != expected:
            raise ValueError("SIM identity changed since baseline capture")
        self.identity_pending = False

    def query(self, command, optional=False, timeout=15):
        if not re.fullmatch(r'AT[+A-Za-z0-9?=,"._ -]*', command):
            raise ValueError("Invalid AT command encoding")
        allowed = (command in QUERIES or command in ("AT+CFUN=0", "AT+CFUN=1", "AT+CFUN=?", "AT+CEER") or
                   re.fullmatch(r'AT\+CG(?:ACT=[01],[1-9][0-9]?|PADDR=[1-9][0-9]?|CONTRDP=[1-9][0-9]?|DCONT=[1-9][0-9]?(?:,"IP(?:V4V6)?","ims")?)', command))
        if not allowed:
            raise ValueError("AT command is outside the acceptance allowlist")
        self.serial.reset_input_buffer()
        self.serial.write((command + "\r").encode())
        lines, deadline = [], time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.serial.readline().decode(errors="replace").strip()
            if not line or line == command:
                continue
            lines.append(line)
            if line == "OK":
                return lines
            if line == "ERROR" or line.startswith(("+CME ERROR", "+CMS ERROR")):
                if optional:
                    return lines
                raise ValueError("Modem rejected " + command.split("=")[0] + ": " + line)
        raise TimeoutError("AT response timeout: " + command.split("=")[0])


def contexts(lines):
    result = {}
    for line in lines:
        if not line.startswith("+CGDCONT:"):
            continue
        fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
        if len(fields) < 3 or not fields[0].isdigit():
            raise ValueError("Malformed modem context response")
        cid = int(fields[0])
        if cid in result or not 0 <= cid <= 255:
            raise ValueError("Duplicate or malformed context ID")
        result[cid] = {"type": fields[1], "dnn": fields[2].lower(), "fields": fields}
    return result


def select_cids(current):
    data = [cid for cid, value in current.items() if value["dnn"] == "oai"]
    ims = [cid for cid, value in current.items() if value["dnn"] == "ims"]
    if len(data) != 1 or len(ims) > 1:
        raise ValueError("Expected one data DNN and at most one IMS DNN")
    if any(not 1 <= cid <= 16 for cid in data + ims):
        raise ValueError("Data/IMS DNN uses a reserved or unsupported operational CID")
    available = [cid for cid in range(2, 17) if cid not in current]
    if not ims and not available:
        raise ValueError("No unused CID for IMS; existing contexts will not be overwritten")
    return data[0], ims[0] if ims else available[0], not bool(ims)


def registered(lines):
    return any(re.match(r"\+C5GREG:\s*\d+\s*,\s*[15](?:,|$)", line) for line in lines)


def set_functionality(modem, value):
    print("UE: setting functionality to " + str(value), flush=True)
    response = modem.query("AT+CFUN=" + str(value), optional=True, timeout=30)
    for _ in range(5):
        observed = modem.query("AT+CFUN?")
        if "+CFUN: " + str(value) in observed:
            if "OK" not in response:
                print("UE: command returned an error but the requested functionality is confirmed by readback", flush=True)
            return
        time.sleep(1)
    raise ValueError("Requested CFUN state was not reached; response: " + "; ".join(response))


def wait_registration(modem):
    deadline = time.monotonic() + 120
    while not registered(modem.query("AT+C5GREG?")):
        if time.monotonic() >= deadline:
            save("registration-failure.json", {"ceer": modem.query("AT+CEER", optional=True)})
            raise TimeoutError("5GS registration did not complete within 120 seconds")
        time.sleep(2)


def resume_minimum(modem):
    if modem.identity_pending:
        set_functionality(modem, 1)
        deadline = time.monotonic() + 30
        while "+CPIN: READY" not in modem.query("AT+CPIN?", optional=True):
            if time.monotonic() >= deadline:
                raise TimeoutError("SIM is not ready after leaving minimum functionality")
            time.sleep(1)
        modem.verify_identity()


def active_cids(lines):
    return {int(match[1]) for line in lines if (match := re.fullmatch(r"\+CGACT:\s*(\d+),\s*1", line))}


def pdu_ip(lines, cid, network):
    for line in lines:
        if line.startswith("+CGPADDR:"):
            fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
            if int(fields[0]) == cid:
                for value in fields[1:]:
                    try:
                        address = ipaddress.ip_address(value)
                    except ValueError:
                        continue
                    if address in ipaddress.ip_network(network) and address not in (
                            ipaddress.ip_network(network).network_address, ipaddress.ip_network(network).broadcast_address):
                        return str(address)
    raise ValueError("CID {} has no address in the selected {} pool".format(cid, network))


def snapshot(modem, profile):
    current = contexts(modem.query("AT+CGDCONT?"))
    data, ims, create = select_cids(current)
    if create or not {data, ims} <= active_cids(modem.query("AT+CGACT?")):
        raise ValueError("Data and IMS contexts are not both active")
    registration = modem.query("AT+C5GREG?")
    if not registered(registration):
        raise ValueError("UE is not registered with 5GS")
    result = {"profile": profile, "at": time.time(), "data_cid": data, "ims_cid": ims,
              "data_ip": pdu_ip(modem.query("AT+CGPADDR=" + str(data)), data, PROFILES[profile]["data"]),
              "ims_ip": pdu_ip(modem.query("AT+CGPADDR=" + str(ims)), ims, PROFILES[profile]["ims"]),
              "qos_verified": False, "sip_verified": False, "registration_5gs": registration,
              "context_details": modem.query("AT+CGCONTRDP=" + str(ims), optional=True)}
    save("snapshot-" + str(time.time_ns()) + ".json", result)
    return result


def diagnose(modem):
    result = {"at": time.time(), "queries": {}}
    for query in ("AT+CFUN?", "AT+CFUN=?", "AT+CPIN?", "AT+CEREG?", "AT+C5GREG?", "AT+COPS?",
                  "AT+CGDCONT?", "AT+CGACT?", 'AT+QENG="servingcell"', "AT+CEER"):
        print("UE: querying " + query, flush=True)
        result["queries"][query] = modem.query(query, optional=True)
    for cid in ue_cids(result["queries"]["AT+CGDCONT?"]):
        query = "AT+CGPADDR=" + str(cid)
        result["queries"][query] = modem.query(query, optional=True)
    save("diagnose-" + str(time.time_ns()) + ".json", result)
    return result


def ue_cids(lines):
    return sorted(cid for cid, context in contexts(lines).items() if 1 <= cid <= 16 and context["dnn"] in ("oai", "ims"))


def prepare():
    if (STATE / "baseline.json").exists():
        maintenance_required()
        print("Existing baseline retained; maintenance is active")
        return
    with console_db() as connection:
        idle(connection)
        original = connection.execute("SELECT value FROM settings WHERE key='maintenance_mode'").fetchone()
    previous_path = STATE / "maintenance-before.json"
    if previous_path.exists():
        previous = json.loads(previous_path.read_text())
    else:
        was_active = run(["systemctl", "is-active", "oai-console.service"]).strip() == "active"
        previous = {"value": original[0] if original else None, "was_active": was_active}
        save("maintenance-before.json", previous)
    set_mode("true")
    try:
        stop_console()
        print("UE: console stopped; capturing original modem and network configuration", flush=True)
        with Modem() as modem:
            responses = {}
            for query in QUERIES:
                print("UE: querying " + query, flush=True)
                responses[query] = modem.query(query, optional=query not in ("AT", "AT+CIMI", "AT+CFUN?", "AT+CGDCONT?", "AT+CGACT?"))
        save("prepare-responses.json", responses)
        imsi = [line for line in responses["AT+CIMI"] if re.fullmatch(r"[0-9]{15}", line)]
        if len(imsi) != 1:
            raise ValueError("Cannot identify one current SIM")
        select_cids(contexts(responses["AT+CGDCONT?"]))
        save("baseline.json", {"at": time.time(), "responses": responses,
                               "addresses": json.loads(run(["ip", "-j", "address"])),
                               "routes": json.loads(run(["ip", "-j", "route", "show", "table", "all"]))})
        save("identity.json", {"imsi": imsi[0]})
        operator = pwd.getpwnam("matt")
        transfer = Path(operator.pw_dir) / "agentic-ocudu-ue/identity.json"
        if transfer.parent.is_symlink() or transfer.parent.stat().st_uid != operator.pw_uid:
            raise ValueError("Identity transfer directory ownership changed")
        fd = os.open(transfer, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump({"imsi": imsi[0]}, output)
            os.fchown(output.fileno(), operator.pw_uid, operator.pw_gid)
        print("UE: restoring original console in maintenance mode", flush=True)
        run(["systemctl", "start", "oai-console.service"], timeout=30)
        maintenance_required()
        print("Original console is in maintenance; private baseline and SIM identity saved")
    except BaseException:
        print("UE: prepare failed; restoring prior maintenance setting", flush=True)
        set_mode(previous["value"])
        if previous["was_active"]:
            run(["systemctl", "start", "--no-block", "oai-console.service"], timeout=10)
            state = run(["systemctl", "show", "oai-console.service", "-p", "ActiveState", "--value"], timeout=5).strip()
            if state != "active":
                print("UE: original restart requested but not yet confirmed; inspect service status", flush=True)
        raise


def ims_ipv4_context(original):
    fields = list(original["fields"])
    if original["type"] != "IPV4V6" or original["dnn"] != "ims" or len(fields) < 4:
        raise ValueError("Only an existing IPv4v6 IMS context can be adapted")
    if fields[3] not in ("0.0.0.0", ".".join(["0"] * 16)):
        raise ValueError("IMS has a configured address; automatic type adjustment refused")
    fields[1], fields[3] = "IP", "0.0.0.0"
    return {"type": "IP", "dnn": "ims", "fields": fields}


def ensure_ims_ipv4(modem):
    current = contexts(modem.query("AT+CGDCONT?"))
    data, ims, create = select_cids(current)
    if create or ims == data:
        raise ValueError("An independent IMS context must exist before type adjustment")
    if current[ims]["type"] == "IP":
        return
    expected = ims_ipv4_context(current[ims])
    if ims in active_cids(modem.query("AT+CGACT?")):
        raise ValueError("IMS is active; refusing to change its PDU type")
    baseline = contexts(json.loads((STATE / "baseline.json").read_text())["responses"]["AT+CGDCONT?"])
    if baseline.get(ims) != current[ims]:
        raise ValueError("IMS configuration differs from the private baseline")
    record = {"cid": ims, "original": current[ims], "adjusted": expected}
    marker = STATE / "modified-ims.json"
    if marker.exists():
        if json.loads(marker.read_text()) != record:
            raise ValueError("An earlier IMS adjustment has different recovery information")
    else:
        # Save recovery information before the modem write, including on command failure.
        save("modified-ims.json", record)
    print("UE: adapting inactive IMS CID {} from IPV4V6 to IP; original configuration saved".format(ims), flush=True)
    modem.query('AT+CGDCONT={},"IP","ims"'.format(ims))
    if contexts(modem.query("AT+CGDCONT?")).get(ims) != expected:
        raise ValueError("IMS type readback or other context settings differ; recovery information retained")


def restore_ims_type(modem, original):
    marker = STATE / "modified-ims.json"
    if not marker.exists():
        return
    record = json.loads(marker.read_text())
    cid = record["cid"]
    if (not 1 <= cid <= 16 or original.get(cid) != record["original"] or
            record["adjusted"] != ims_ipv4_context(record["original"])):
        raise ValueError("IMS recovery information does not match the original baseline")
    current = contexts(modem.query("AT+CGDCONT?"))
    if current.get(cid) == record["original"]:
        return
    if current.get(cid) != record["adjusted"]:
        raise ValueError("Adjusted IMS context ownership changed; refusing restoration")
    if cid in active_cids(modem.query("AT+CGACT?")):
        modem.query("AT+CGACT=0," + str(cid), timeout=45)
        if cid in active_cids(modem.query("AT+CGACT?")):
            raise ValueError("IMS did not deactivate; refusing to restore its type")
    print("UE: restoring original IMS IPV4V6 configuration", flush=True)
    modem.query('AT+CGDCONT={},"IPV4V6","ims"'.format(cid))
    if contexts(modem.query("AT+CGDCONT?")).get(cid) != record["original"]:
        raise ValueError("Original IMS settings have not fully recovered")


def ensure_ims_profile(modem, profile):
    current = contexts(modem.query("AT+CGDCONT?"))
    data, ims, create = select_cids(current)
    if create or ims == data:
        raise ValueError("An independent IMS context must exist before profile adjustment")
    if current[ims]["type"] == PROFILES[profile]["ims_type"]:
        return
    if ims in active_cids(modem.query("AT+CGACT?")):
        raise ValueError("IMS is active with another PDU type; refusing automatic adjustment")
    if profile == "ocudu":
        ensure_ims_ipv4(modem)
        return
    baseline = contexts(json.loads((STATE / "baseline.json").read_text())["responses"]["AT+CGDCONT?"])
    if baseline.get(ims, {}).get("type") != "IPV4V6" or not (STATE / "modified-ims.json").is_file():
        raise ValueError("Legacy IMS requires IPV4V6, but no matching original recovery record exists")
    restore_ims_type(modem, baseline)
    if contexts(modem.query("AT+CGDCONT?")).get(ims) != baseline[ims]:
        raise ValueError("Legacy IMS context has not recovered its original settings")


def connect(modem, profile, reconnect=False):
    resume_minimum(modem)
    current = contexts(modem.query("AT+CGDCONT?"))
    data, ims, create = select_cids(current)
    active = active_cids(modem.query("AT+CGACT?"))
    if reconnect:
        if create or current[ims]["type"] != PROFILES[profile]["ims_type"]:
            raise ValueError("Prepare the selected IMS context type before requesting a reconnect")
        save("reconnect-before-" + str(time.time_ns()) + ".json",
             {"at": time.time(), "profile": profile, "contexts": current, "active_cids": sorted(active)})
        print("UE: explicit one-time reconnect; data and IMS sessions will be interrupted", flush=True)
    data_ready = False
    if data in active:
        try:
            pdu_ip(modem.query("AT+CGPADDR=" + str(data)), data, PROFILES[profile]["data"])
            data_ready = registered(modem.query("AT+C5GREG?"))
        except ValueError:
            pass
    if data_ready and not reconnect:
        print("UE: correct data PDU is already active; preserving it", flush=True)
    else:
        set_functionality(modem, 0)
        time.sleep(2)
        set_functionality(modem, 1)
        wait_registration(modem)
        if data not in active_cids(modem.query("AT+CGACT?")):
            modem.query("AT+CGACT=1," + str(data), timeout=45)
        pdu_ip(modem.query("AT+CGPADDR=" + str(data)), data, PROFILES[profile]["data"])
    if create:
        save("created-ims.json", {"cid": ims})
        modem.query('AT+CGDCONT={},"{}","ims"'.format(ims, PROFILES[profile]["ims_type"]))
    ensure_ims_profile(modem, profile)
    if ims not in active_cids(modem.query("AT+CGACT?")):
        print("UE: activating IMS CID " + str(ims), flush=True)
        modem.query("AT+CGACT=1," + str(ims), timeout=45)
    return snapshot(modem, profile)


def usb_parent(path):
    device = path.resolve(strict=True)
    for parent in (device, *device.parents):
        if (parent / "idVendor").is_file() and (parent / "idProduct").is_file():
            return parent
    raise ValueError("Cannot identify the modem USB parent")


def data_interface():
    try:
        modem = usb_parent(SYS_TTY / PORT.resolve(strict=True).name / "device")
        if ((modem / "idVendor").read_text().strip().lower(),
                (modem / "idProduct").read_text().strip().lower()) != ("2c7c", "0801"):
            raise ValueError("AT port does not belong to the reviewed RM520N USB device")
        matches = []
        for link in SYS_NET.iterdir():
            driver = link / "device/driver"
            if not driver.exists() or driver.resolve().name not in ("cdc_ether", "rndis_host"):
                continue
            if usb_parent(link / "device") == modem:
                matches.append(link.name)
    except OSError as error:
        raise ValueError("Modem USB interfaces are unavailable; wait for enumeration") from error
    if len(matches) != 1:
        raise ValueError("Expected one RNDIS interface on the same USB modem as the AT port; found " + str(len(matches)))
    return matches[0]


def verify_data_route(target, source, interface):
    route = json.loads(run(["ip", "-j", "route", "get", target, "from", source]))
    if len(route) != 1 or route[0].get("dev") != interface or route[0].get("gateway") != GATEWAY:
        raise ValueError("Probe would not use the UE data interface")


@contextmanager
def data_route(profile):
    target = PROFILES[profile]["target"]
    interface = data_interface()
    print("UE: using modem data interface " + interface, flush=True)
    addresses = json.loads(run(["ip", "-j", "-4", "address", "show", "dev", interface]))
    sources = [item["local"] for device in addresses for item in device["addr_info"] if item["scope"] == "global"]
    if len(sources) != 1 or ipaddress.ip_address(sources[0]) not in ipaddress.ip_network("192.168.224.0/22"):
        raise ValueError("RNDIS has no unique expected DHCP address")
    source = sources[0]
    existing = json.loads(run(["ip", "-j", "-4", "route", "show", "exact", target + "/32"]))
    if existing and (len(existing) != 1 or existing[0].get("dev") != interface or existing[0].get("gateway") != GATEWAY):
        raise ValueError("Probe route already belongs to another interface; refusing replacement")
    added = not existing
    if added:
        run(["ip", "route", "add", target + "/32", "via", GATEWAY, "dev", interface, "proto", "186"])
    try:
        verify_data_route(target, source, interface)
        yield target, source, interface
    finally:
        if added:
            run(["ip", "route", "del", target + "/32", "via", GATEWAY, "dev", interface, "proto", "186"])


def probe(modem, profile, direction="both"):
    if direction not in ("both", "uplink", "downlink"):
        raise ValueError("Unknown throughput direction")
    selected = [(name, extra) for name, extra in (("uplink", []), ("downlink", ["-R"]))
                if direction in ("both", name)]
    result = snapshot(modem, profile)
    record_name = "probe-" + str(time.time_ns()) + ".json"
    result.update({"phase": "ping", "passed": False, "bidirectional_passed": False,
                   "directions": [name for name, _ in selected], "measurements": {}})
    try:
        with data_route(profile) as (target, source, interface):
            result.update(data_interface=interface, source_address=source)
            result["ping"] = run(["ping", "-I", interface, "-c", "5", "-W", "2", target], timeout=15)
            for index, (direction, extra) in enumerate(selected):
                if index:
                    result.update(phase="settling", direction_settle_seconds=DIRECTION_SETTLE_SECONDS)
                    save(record_name, result)
                    print("UE: allowing 3 seconds for the previous iperf3 session to close", flush=True)
                    time.sleep(DIRECTION_SETTLE_SECONDS)
                verify_data_route(target, source, interface)
                result["phase"] = direction
                print("UE: testing " + direction + " through the UE data interface", flush=True)
                details = result["measurements"][direction] = {}
                try:
                    completed = subprocess.run(["iperf3", "-c", target, "-B", source, "-t", "5", "--json", *extra],
                                               capture_output=True, text=True, timeout=20, check=False)
                except subprocess.TimeoutExpired as error:
                    details["timed_out"] = True
                    for key, value in (("stdout", error.stdout), ("stderr", error.stderr)):
                        details[key] = value.decode(errors="replace") if isinstance(value, bytes) else value or ""
                    raise TimeoutError("UE " + direction + " iperf3 exceeded 20 seconds") from error
                details.update({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
                try:
                    measured = json.loads(completed.stdout)
                except ValueError:
                    measured = {}
                if not isinstance(measured, dict):
                    measured = {}
                if completed.returncode or measured.get("error"):
                    reason = str(measured.get("error") or completed.stderr.strip() or "no error description returned")
                    raise ValueError("UE {} iperf3 failed (exit {}): {}".format(
                        direction, completed.returncode, " ".join(reason.split())[:500]))
                received = measured.get("end", {}).get("sum_received", {})
                values = [received.get(key) for key in ("bytes", "bits_per_second")]
                if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in values):
                    raise ValueError("UE " + direction + " iperf3 returned no valid positive receiver result")
                result[direction + "_bps"] = received["bits_per_second"]
                verify_data_route(target, source, interface)
                save(record_name, result)
                print("UE: {} {:.3f} Mbps".format(direction, received["bits_per_second"] / 1e6), flush=True)
        result.update({"phase": "complete", "passed": True, "bidirectional_passed": len(selected) == 2})
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        save(record_name, result)
        print("UE: private probe record: " + str(STATE / record_name), flush=True)
    return result


def ims_cycles(modem, profile):
    before = snapshot(modem, profile)
    cycles = []
    with data_route(profile) as (target, source, interface):
        for _ in range(3):
            modem.query("AT+CGACT=0," + str(before["ims_cid"]), timeout=45)
            active = active_cids(modem.query("AT+CGACT?"))
            if before["ims_cid"] in active or before["data_cid"] not in active:
                raise ValueError("IMS release affected data or IMS remained active")
            run(["ping", "-I", interface, "-c", "3", "-W", "2", target], timeout=10)
            modem.query("AT+CGACT=1," + str(before["ims_cid"]), timeout=45)
            after = snapshot(modem, profile)
            if (after["data_cid"], after["data_ip"]) != (before["data_cid"], before["data_ip"]):
                raise ValueError("Data context changed across IMS recovery")
            run(["ping", "-I", interface, "-c", "3", "-W", "2", target], timeout=10)
            cycles.append(after)
    save("ims-cycles-" + str(time.time_ns()) + ".json", cycles)
    return {"cycles_passed": len(cycles), "data_cid": before["data_cid"], "data_ip": before["data_ip"]}


def restore(modem):
    resume_minimum(modem)
    baseline = json.loads((STATE / "baseline.json").read_text())["responses"]
    was_on = "+CFUN: 1" in baseline["AT+CFUN?"]
    if not was_on and "+CFUN: 0" not in baseline["AT+CFUN?"]:
        raise ValueError("Original modem mode needs manual restoration")
    original = contexts(baseline["AT+CGDCONT?"])
    restore_ims_type(modem, original)
    current = contexts(modem.query("AT+CGDCONT?"))
    for cid, context in original.items():
        if cid not in current or current[cid]["fields"][:3] != context["fields"][:3]:
            raise ValueError("Original context changed unexpectedly; manual recovery required")
    created = STATE / "created-ims.json"
    if created.exists():
        cid = json.loads(created.read_text())["cid"]
        if cid in original or current.get(cid, {}).get("dnn") != "ims":
            raise ValueError("Created IMS context ownership changed; refusing deletion")
        if cid in active_cids(modem.query("AT+CGACT?")):
            modem.query("AT+CGACT=0," + str(cid), timeout=45)
        modem.query("AT+CGDCONT=" + str(cid))
    set_functionality(modem, 0)
    if was_on:
        time.sleep(2)
        set_functionality(modem, 1)
        wait_registration(modem)
        expected = active_cids(baseline["AT+CGACT?"])
        for cid in active_cids(modem.query("AT+CGACT?")) - expected:
            modem.query("AT+CGACT=0," + str(cid), timeout=45)
        for cid in expected:
            if cid not in active_cids(modem.query("AT+CGACT?")):
                modem.query("AT+CGACT=1," + str(cid), timeout=45)
        if expected != active_cids(modem.query("AT+CGACT?")):
            raise ValueError("Original active contexts have not recovered")
        for cid in expected:
            dnn = original[cid]["dnn"]
            if dnn in ("oai", "ims"):
                pdu_ip(modem.query("AT+CGPADDR=" + str(cid)), cid,
                       PROFILES["legacy"]["data" if dnn == "oai" else "ims"])
    if contexts(modem.query("AT+CGDCONT?")) != original:
        raise ValueError("Full original context configuration has not been restored")
    if created.exists():
        created.unlink()
    (STATE / "modified-ims.json").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "identity", "diagnose", "status", "connect", "probe", "ims-cycles", "restore"))
    parser.add_argument("--profile", choices=tuple(PROFILES), default="ocudu")
    parser.add_argument("--direction", choices=("both", "uplink", "downlink"), default="both",
                        help="Probe direction; a single direction does not pass bidirectional acceptance")
    parser.add_argument("--show-context", action="store_true",
                        help="Include the IMS CGCONTRDP response in status/probe output")
    parser.add_argument("--reconnect", action="store_true",
                        help="Explicitly reconnect once during connect, interrupting both PDU sessions")
    args = parser.parse_args()
    if args.action != "probe" and args.direction != "both":
        parser.error("--direction is only available for probe")
    if args.show_context and args.action not in ("status", "probe"):
        parser.error("--show-context is only available for status/probe")
    if args.reconnect and args.action != "connect":
        parser.error("--reconnect is only available for connect")
    if os.geteuid() != 0:
        raise ValueError("Run in a sudo-authorized Jetson terminal")
    os.umask(0o077)
    STATE.mkdir(mode=0o700, exist_ok=True)
    if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
        raise ValueError("Private acceptance directory ownership/permissions are invalid")
    with (STATE / "serial.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "prepare":
            prepare()
            return
        if args.action == "identity":
            # Output is intended only for a private redirected transfer, never chat or Git.
            print((STATE / "identity.json").read_text(), end="")
            return
        if not (STATE / "baseline.json").is_file():
            raise ValueError("Capture a private baseline before accessing the modem")
        with Modem(check_identity=args.action != "diagnose", allow_minimum=args.action in ("connect", "restore")) as modem:
            if args.action == "diagnose":
                result = diagnose(modem)
            elif args.action == "restore":
                restore(modem)
                result = {"modem_configuration_restored": True}
            elif args.action == "probe":
                result = probe(modem, args.profile, args.direction)
            elif args.action == "connect":
                result = connect(modem, args.profile, reconnect=args.reconnect)
            else:
                operation = {"status": snapshot, "ims-cycles": ims_cycles}[args.action]
                result = operation(modem, args.profile)
        if args.action == "restore":
            previous = json.loads((STATE / "maintenance-before.json").read_text())
            stop_console()
            set_mode(previous["value"])
            if previous["was_active"]:
                run(["systemctl", "start", "oai-console.service"], timeout=90)
            result["original_maintenance_mode_restored"] = True
            save("restored.json", result)
        hidden = {"ping", "measurements"}
        if not args.show_context:
            hidden.add("context_details")
        print(json.dumps({key: value for key, value in result.items() if key not in hidden}))


if __name__ == "__main__":
    main()
