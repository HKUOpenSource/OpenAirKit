"""RM520N data-only adapter with a fixed query and mutation surface."""
import csv
import fcntl
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import time

from .hardware import discover


QUERIES = frozenset({
    "AT", "ATI", "AT+CPIN?", "AT+CIMI", "AT+CFUN?", "AT+C5GREG?", "AT+CEREG?",
    "AT+CGDCONT?", "AT+CGACT?", 'AT+QENG="servingcell"', "AT+CEER",
    'AT+QNWPREFCFG="mode_pref"', 'AT+QNWPREFCFG="nr5g_disable_mode"',
    'AT+QNWPREFCFG="nr5g_band"', 'AT+QCFG="usbnet"', 'AT+QCFG="usbspeed"',
})


def contexts(lines):
    result = {}
    for line in lines:
        if not line.startswith("+CGDCONT:"):
            continue
        fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
        if len(fields) < 3 or not fields[0].isdigit():
            raise ValueError("Malformed context response")
        cid = int(fields[0])
        if not 0 <= cid <= 255 or cid in result:
            raise ValueError("Duplicate or invalid context ID")
        result[cid] = {"cid": cid, "type": fields[1].upper(), "dnn": fields[2].lower(),
                       "fields": fields}
    return result


def select_data(current, data):
    matches = [cid for cid, value in current.items() if value["dnn"] == data["dnn"]]
    if len(matches) > 1:
        raise ValueError("Duplicate data DNN contexts")
    if matches:
        if not data["cid_min"] <= matches[0] <= data["cid_max"]:
            raise ValueError("Data DNN uses a reserved CID")
        return matches[0], False
    available = [cid for cid in range(data["cid_min"], data["cid_max"] + 1) if cid not in current]
    if not available:
        raise ValueError("No free data CID in the allowed range")
    return available[0], True


def active(lines):
    return {int(match[1]) for line in lines
            if (match := re.fullmatch(r"\+CGACT:\s*(\d+)\s*,\s*1", line))}


def registration(c5greg, cereg):
    def state(lines, prefix):
        match = next((re.match(r"\+" + prefix + r":\s*\d+\s*,\s*(\d+)(?:,|$)", line)
                      for line in lines if line.startswith("+" + prefix + ":")), None)
        return int(match[1]) if match else None
    five = state(c5greg, "C5GREG")
    eps = state(cereg, "CEREG")
    return {"registered_5gs": five in (1, 5), "c5greg": five, "cereg": eps,
            "source": "AT+C5GREG", "disagrees_with_cereg": five is not None and eps is not None
            and (five in (1, 5)) != (eps in (1, 5))}


def address(lines, cid, network):
    found = []
    for line in lines:
        if not line.startswith("+CGPADDR:"):
            continue
        fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
        if not fields or fields[0] != str(cid):
            continue
        for field in fields[1:]:
            try:
                value = ipaddress.ip_address(field)
            except ValueError:
                continue
            if value.version == 4 and not value.is_unspecified:
                found.append(str(value))
    valid = [value for value in found if ipaddress.ip_address(value) in ipaddress.ip_network(network)]
    return valid[0] if len(valid) == 1 else None


def context_address(lines, cid, dnn, network):
    found = []
    for line in lines:
        if not line.startswith("+CGCONTRDP:"):
            continue
        fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
        if len(fields) < 4 or fields[0] != str(cid) or fields[2].lower() != dnn:
            continue
        try:
            value = ipaddress.ip_address(fields[3])
        except ValueError:
            continue
        if value.version == 4 and value in ipaddress.ip_network(network):
            found.append(str(value))
    return found[0] if len(found) == 1 else None


def serving_cell(lines):
    for line in lines:
        if not line.startswith("+QENG:") or "NR5G-SA" not in line:
            continue
        fields = next(csv.reader([line.split(":", 1)[1].strip()], skipinitialspace=True))
        try:
            return {"state": fields[1], "rat": fields[2], "plmn": fields[4] + fields[5],
                    "cell_id": fields[6], "pci": int(fields[7]), "tac": int(fields[8]),
                    "ssb_arfcn": int(fields[9]), "band": int(fields[10]),
                    "rsrp_dbm": float(fields[12]), "rsrq_db": float(fields[13]),
                    "sinr_db": float(fields[14])}
        except (IndexError, ValueError):
            continue
    return {}


class Modem:
    def __init__(self, config, serial_factory=None):
        self.config = config
        self.serial_factory = serial_factory
        self.port = None
        self.lock = None
        self.discovered = None
        self.power_restore_authorized = False

    def open(self):
        if self.port is not None and self.port.is_open:
            return
        self.discovered = discover(self.config)
        lock_path = Path(self.config["device"]["serial_lock"])
        lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = lock_path.open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.serial_factory is None:
                import serial
                self.serial_factory = serial.Serial
            self.port = self.serial_factory(self.discovered["at_port"], 115200, timeout=.2,
                                            write_timeout=2, exclusive=True)
            fcntl.ioctl(self.port.fileno(), 0x540C)
            self.query("AT")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.port is not None:
            self.port.close()
        if self.lock is not None:
            self.lock.close()
        self.port = self.lock = None

    def exchange(self, command, timeout=3, optional=False):
        self.open()
        self.port.reset_input_buffer()
        self.port.write((command + "\r").encode())
        lines, pending, deadline = [], b"", time.monotonic() + timeout
        while time.monotonic() < deadline:
            pending += self.port.read(1024)
            if len(pending) > 16384:
                raise ValueError("Oversized modem response")
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode(errors="replace").strip()
                if not line or line == command:
                    continue
                lines.append(line)
                if line == "OK":
                    return lines
                if line == "ERROR" or line.startswith(("+CME ERROR", "+CMS ERROR")):
                    if optional:
                        return lines
                    raise ValueError("Modem rejected " + command.split("=")[0] + ": " + line)
        raise TimeoutError("AT command timed out: " + command.split("=")[0])

    def query(self, command, timeout=3, optional=False):
        if command not in QUERIES and not re.fullmatch(r"AT\+(?:CGPADDR|CGCONTRDP)=(?:[1-9]|1[0-6])", command):
            raise ValueError("Query not allow-listed")
        return self.exchange(command, timeout, optional)

    def fingerprint(self):
        identity = next((line for line in self.query("AT+CIMI") if re.fullmatch(r"\d{14,16}", line)), None)
        if not identity:
            raise ValueError("SIM identity unavailable")
        return hashlib.sha256(identity.encode()).hexdigest(), "SIM ****" + identity[-4:]

    def write(self, operation, cid=None):
        if not self.config.get("commissioned"):
            raise ValueError("Commissioning checks have not passed")
        if operation != "cfun1" or not self.power_restore_authorized:
            fingerprint, _ = self.fingerprint()
            if fingerprint != self.config.get("sim_sha256"):
                raise ValueError("SIM identity mismatch")
        data = self.config["network"]["data"]
        if operation in {"context", "activate", "deactivate"}:
            if type(cid) is not int or not data["cid_min"] <= cid <= data["cid_max"]:
                raise ValueError("CID outside the data operation range")
            current = contexts(self.query("AT+CGDCONT?"))
            selected, create = select_data(current, data)
            if cid != selected:
                raise ValueError("CID is not the selected data context")
            if operation == "context":
                if not create and current[cid]["dnn"] != data["dnn"]:
                    raise ValueError("CID belongs to another context")
                if cid in active(self.query("AT+CGACT?")):
                    raise ValueError("Deactivate the data context before changing it")
                command = 'AT+CGDCONT={},"{}","{}"'.format(cid, data["pdu_type"], data["dnn"])
            else:
                if create:
                    raise ValueError("Data context is not configured")
                command = "AT+CGACT={},{}".format(int(operation == "activate"), cid)
        else:
            commands = {"cfun0": "AT+CFUN=0", "cfun1": "AT+CFUN=1",
                        "automatic": "AT+COPS=0", "nr5g": 'AT+QNWPREFCFG="mode_pref","NR5G"',
                        "sa": 'AT+QNWPREFCFG="nr5g_disable_mode",0',
                        "band78": 'AT+QNWPREFCFG="nr5g_band",78'}
            if operation not in commands:
                raise ValueError("Operation not allow-listed")
            command = commands[operation]
        result = self.exchange(command, 45 if operation in {"activate", "deactivate", "automatic"} else 30,
                               optional=operation.startswith("cfun"))
        if operation.startswith("cfun"):
            expected = "+CFUN: " + operation[-1]
            if expected not in self.query("AT+CFUN?"):
                raise ValueError("CFUN acknowledge/readback did not confirm the target")
            self.power_restore_authorized = operation == "cfun0"
        return result

    def snapshot(self):
        at = time.time()
        data = self.config["network"]["data"]
        lines = {query: self.query(query, optional=query not in {"AT", "AT+CGDCONT?", "AT+CGACT?"})
                 for query in QUERIES if query not in {"AT+CIMI"}}
        fingerprint, identity = self.fingerprint()
        current = contexts(lines["AT+CGDCONT?"])
        cid, create = select_data(current, data)
        enabled = active(lines["AT+CGACT?"])
        paddr = self.query("AT+CGPADDR=" + str(cid), optional=True) if not create else []
        detail = self.query("AT+CGCONTRDP=" + str(cid), optional=True) if not create else []
        data_ip = address(paddr, cid, data["ue_pool"]) or context_address(
            detail, cid, data["dnn"], data["ue_pool"])
        reg = registration(lines["AT+C5GREG?"], lines["AT+CEREG?"])
        session = {"cid": cid, "dnn": data["dnn"], "pdu_type": current.get(cid, {}).get("type"),
                   "configured": not create, "active": cid in enabled, "address": data_ip,
                   "pool_valid": data_ip is not None, "at": at}
        return {"at": at, "identity": identity, "sim_ready": "+CPIN: READY" in lines["AT+CPIN?"],
                "sim_matches": fingerprint == self.config.get("sim_sha256"), **reg,
                "radio": serving_cell(lines['AT+QENG="servingcell"']), "data_session": session,
                "other_contexts": [{"cid": cid, "type": value["type"], "dnn": value["dnn"]}
                                   for cid, value in sorted(current.items()) if cid != session["cid"]],
                "data_interface": self.discovered["data_interface"],
                "firmware": " ".join(lines["ATI"][:-1])[:180],
                "query_quality": {query: "ok" if "OK" in value else "unsupported"
                                  for query, value in lines.items()}}
