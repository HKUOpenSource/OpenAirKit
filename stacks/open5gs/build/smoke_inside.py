#!/usr/bin/env python3
"""Check empty Open5GS info endpoints in an isolated network namespace."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import urllib.request


def configurations():
    plmn = {"mcc": "460", "mnc": "03"}
    client = {"nrf": [{"uri": "http://127.0.0.10:7777"}]}
    return {
        "nrf": {"sbi": {"server": [{"address": "127.0.0.10", "port": 7777}]}},
        "amf": {
            "sbi": {"server": [{"address": "127.0.0.5", "port": 7777}], "client": client},
            "ngap": {"server": [{"address": "127.0.0.5"}]},
            "metrics": {"server": [{"address": "127.0.0.5", "port": 9090}]},
            "guami": [{"plmn_id": plmn, "amf_id": {"region": 2, "set": 1}}],
            "tai": [{"plmn_id": plmn, "tac": 1}],
            "plmn_support": [{"plmn_id": plmn, "s_nssai": [{"sst": 1}]}],
            "security": {"integrity_order": ["NIA2", "NIA1"], "ciphering_order": ["NEA0"]},
            "network_name": {"full": "Agentic-OCUDU Lab"},
            "amf_name": "aoc-lab-amf", "time": {"t3512": {"value": 540}}
        },
        "smf": {
            "sbi": {"server": [{"address": "127.0.0.4", "port": 7777}], "client": client},
            "pfcp": {"server": [{"address": "127.0.0.4"}]},
            "gtpc": {"server": [{"address": "127.0.0.4"}]},
            "gtpu": {"server": [{"address": "127.0.0.4"}]},
            "metrics": {"server": [{"address": "127.0.0.4", "port": 9090}]},
            "session": [{"subnet": "10.0.0.0/24", "gateway": "10.0.0.1", "dnn": "oai"}],
            "dns": ["1.1.1.1"], "mtu": 1400,
            "info": [{"s_nssai": [{"sst": 1, "dnn": ["oai"]}]}]
        }
    }


def main():
    children = []
    result = {"scope": "no-rf-empty-core", "endpoints": {}, "passed": False}
    result["version"] = subprocess.check_output(
        ["/opt/open5gs/bin/open5gs-amfd", "-v"], text=True, timeout=10).strip()
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory() as temp:
        try:
            for nf, body in configurations().items():
                path = Path(temp) / (nf + ".yaml")
                path.write_text(json.dumps({"logger": {"level": "warn"},
                                            "global": {"max": {"ue": 32}}, nf: body}))
                process = subprocess.Popen(["/opt/open5gs/bin/open5gs-" + nf + "d", "-c", str(path)],
                                           stdout=subprocess.DEVNULL, stderr=None, start_new_session=True)
                children.append((nf, process))
            for host, endpoint in (("127.0.0.5", "gnb-info"), ("127.0.0.5", "ue-info"),
                                   ("127.0.0.4", "pdu-info"), ("127.0.0.5", "metrics"),
                                   ("127.0.0.4", "metrics")):
                deadline = time.monotonic() + 30
                while True:
                    if any(process.poll() is not None for _, process in children):
                        raise RuntimeError("NF exited before endpoint validation")
                    try:
                        with http.open("http://" + host + ":9090/" + endpoint, timeout=2) as response:
                            data = response.read().decode()
                        if endpoint == "metrics":
                            if "# HELP" not in data:
                                raise ValueError("Invalid Prometheus response")
                            value = {"format": "prometheus", "nonempty": True}
                        else:
                            value = json.loads(data)
                            if not isinstance(value, dict) or value.get("items") != []:
                                raise ValueError("Unexpected empty-core info response")
                        result["endpoints"][host + "/" + endpoint] = value
                        break
                    except (OSError, ValueError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.25)
            result["passed"] = True
        finally:
            result["shutdown"] = {}
            for _, process in reversed(children):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for name, process in reversed(children):
                forced = False
                try:
                    code = process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    forced = True
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait(timeout=5)
                result["shutdown"][name] = {"returncode": code, "forced": forced}
                if forced or code != 0:
                    result["passed"] = False
            print(json.dumps(result), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
