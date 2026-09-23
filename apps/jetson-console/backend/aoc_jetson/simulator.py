"""Explicit offline fixture. Hardware failures never select this simulator."""
import copy
import time


class SimModem:
    def __init__(self):
        self.contexts = {1: {"cid": 1, "type": "IP", "dnn": "oai"},
                         2: {"cid": 2, "type": "IPV4V6", "dnn": "ims"},
                         3: {"cid": 3, "type": "IPV4V6", "dnn": "sos"},
                         22: {"cid": 22, "type": "IPV4V6", "dnn": ""}}
        self.active = {1}
        self.registered = True
        self.failure = None
        self.calls = []
        self.functionality = 1

    def close(self):
        pass

    def fingerprint(self):
        return "0" * 64, "SIM ****0001"

    def query(self, command, **_kwargs):
        if command == "AT+CGDCONT?":
            return ['+CGDCONT: {},"{}","{}"'.format(cid, value["type"], value["dnn"])
                    for cid, value in sorted(self.contexts.items())] + ["OK"]
        if command == "AT+CGACT?":
            return ["+CGACT: {},{}".format(cid, int(cid in self.active))
                    for cid in sorted(self.contexts)] + ["OK"]
        if command == "AT+CFUN?":
            return ["+CFUN: " + str(self.functionality), "OK"]
        return ["OK"]

    def write(self, operation, cid=None):
        self.calls.append((operation, cid))
        if self.failure == operation:
            raise ValueError("Simulated modem rejection")
        if operation == "context":
            self.contexts[cid] = {"cid": cid, "type": "IP", "dnn": "oai"}
        elif operation == "activate":
            self.active.add(cid)
        elif operation == "deactivate":
            self.active.discard(cid)
        elif operation == "cfun0":
            self.functionality = 0
            self.registered = False
            self.active.clear()
        elif operation == "cfun1":
            self.functionality = 1
            self.registered = True
        return ["OK"]

    def snapshot(self):
        data = next((value for value in self.contexts.values() if value["dnn"] == "oai"), None)
        cid = data["cid"] if data else 1
        return {"at": time.time(), "identity": "SIM ****0001", "sim_ready": True,
                "sim_matches": True, "registered_5gs": self.registered, "c5greg": 1 if self.registered else 0,
                "cereg": 0, "disagrees_with_cereg": self.registered, "source": "AT+C5GREG",
                "radio": {"rat": "NR5G-SA", "state": "NOCONN", "plmn": "46003", "pci": 666,
                          "band": 78, "ssb_arfcn": 643104, "rsrp_dbm": -96, "rsrq_db": -10,
                          "sinr_db": 12},
                "data_session": {"cid": cid, "dnn": "oai", "pdu_type": data["type"] if data else None,
                                 "configured": data is not None, "active": cid in self.active,
                                 "address": "10.0.0.2" if cid in self.active else None,
                                 "pool_valid": cid in self.active, "at": time.time()},
                "other_contexts": [copy.deepcopy(value) for key, value in sorted(self.contexts.items())
                                   if not data or key != data["cid"]],
                "data_interface": "usb-rndis", "firmware": "Offline RM520N fixture",
                "query_quality": {}}


class SimNetwork:
    def __init__(self):
        self.failure = None
        self.mode = "5g"
        self.calls = []

    def action(self, action, cancel=None):
        self.calls.append(action)
        if self.failure == action:
            raise ValueError("Simulated protected route failure")
        if action == "fallback":
            self.mode = "wifi-available"
        elif action == "promote":
            self.mode = "5g"
        return {"mode": self.mode, "management_protected": True, "mutations": 0}

    def snapshot(self):
        return {"at": time.time(), "quality": "ok", "management_protected": True, "data_interface": "usb-rndis",
                "data_address": "192.168.225.88", "wifi_interface": "wifi0",
                "wifi_address": "192.0.2.10", "tailscale_interface": "tailscale0",
                "ipv4_egress": "usb-rndis", "rx_bps": 19e6, "tx_bps": 5e6,
                "ipv6": {"quality": "unavailable", "reason": "IPv6 data path is not verified"}}

    def probe(self, kind, cancel=None):
        return {"at": time.time(), "kind": kind,
                "state": "failed" if self.failure == "probe" else "ok",
                "latency_ms": 12.5, "jitter_ms": 1.2, "loss_pct": 0,
                "interface": "usb-rndis", "source": "192.168.225.88"}
