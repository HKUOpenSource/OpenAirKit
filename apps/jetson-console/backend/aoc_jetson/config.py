import copy
import hashlib
import ipaddress
import json
from pathlib import Path


REFERENCE = {
    "plmn": "46003",
    "tac": 1,
    "slice": {"sst": 1},
    "data": {"dnn": "oai", "pdu_type": "IP", "ue_pool": "10.0.0.0/24",
             "qos_5qi": 9, "cid_min": 1, "cid_max": 16},
    "user_plane": {"rndis_gateway": "192.168.225.1", "upf_probe": "10.0.0.1",
                   "ext_dn": "172.28.81.15", "public_probe": "8.8.8.8", "iperf_port": 5201},
    "radio": {"band": 78, "channel_bandwidth_mhz": 20, "common_scs_khz": 30,
              "carrier_arfcn": 643392, "pci": 666, "ssb_arfcn_policy": "observe_only"},
}
DEVICE = {"usb_vendor_id": "2c7c", "usb_product_id": "0801",
          "at_interface_number": "02", "serial_lock": "/var/lib/agentic-ocudu/v2-ue/serial.lock"}


def revision(value):
    public_value = {key: item for key, item in value.items()
                    if key not in {"release", "sim_sha256", "revision"}}
    return hashlib.sha256(json.dumps(public_value, sort_keys=True).encode()).hexdigest()[:16]


def validate(value):
    result = copy.deepcopy(value)
    if result.get("schema_version") != 2 or result.get("name") != "agentic-ocudu-jetson-v2":
        raise ValueError("Unsupported Jetson configuration schema")
    if result.get("network") != REFERENCE:
        raise ValueError("Network contract differs from the verified V2 deployment")
    if result.get("device") != DEVICE:
        raise ValueError("Unexpected modem discovery contract")
    management = result.get("management", {})
    if management.get("wifi_interface") != "auto":
        name = management.get("wifi_interface")
        if not isinstance(name, str) or not name or len(name) > 15:
            raise ValueError("Invalid commissioned Wi-Fi interface")
    if management.get("tailscale_interface") != "tailscale0":
        raise ValueError("Unexpected management tunnel interface")
    ipaddress.IPv4Address(management.get("spark_address", ""))
    for key in ("state_dir", "web_state_dir", "agent_socket"):
        path = Path(result.get(key, ""))
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("Runtime paths must be absolute")
    for key in ("commissioned", "management_verified"):
        if type(result.get(key)) is not bool:
            raise ValueError(key + " must be boolean")
    fingerprint = result.get("sim_sha256")
    if fingerprint is not None and (not isinstance(fingerprint, str) or len(fingerprint) != 64
                                    or any(char not in "0123456789abcdef" for char in fingerprint)):
        raise ValueError("Invalid private SIM fingerprint")
    result["revision"] = revision(result)
    return result


def load(path):
    return validate(json.loads(Path(path).read_text()))


def public(config):
    return {"schema_version": config["schema_version"], "name": config["name"],
            "revision": config["revision"], "network": copy.deepcopy(config["network"]),
            "release": config.get("release", "development"),
            "commissioned": config["commissioned"],
            "management_verified": config["management_verified"],
            "sim_fingerprint_configured": bool(config.get("sim_sha256")),
            "route_policy": "RNDIS-bound IPv4 with protected management fallback"}
