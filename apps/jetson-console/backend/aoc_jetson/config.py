import copy
import hashlib
import ipaddress
import json
import re
from pathlib import Path


REFERENCE = {"plmn": "46003", "slice": {"sst": 1},
             "data": {"dnn": "oai", "pdu_type": "IP", "ue_pool": "10.0.0.0/24",
                      "qos_5qi": 9, "cid_min": 1, "cid_max": 16}}
SELECTION = {"rat": "NR5G-SA", "band": 78, "pci": None, "ssb_arfcn": None,
             "mode": "observe_only"}
DIAGNOSTICS = {"rndis_gateway": "192.168.225.1", "upf_probe": "10.0.0.1",
               "ext_dn": "172.28.81.15", "public_probe": "8.8.8.8",
               "required": ["gateway", "upf", "ext_dn"]}
RECOVERY = {"natural_wait_seconds": 120, "cooldown_seconds": 300, "max_attempts": 2}


def migrate(value):
    """One-way on-disk migration; runtime accepts only schema 3."""
    result = copy.deepcopy(value)
    if result.get("schema_version") == 2:
        network = result["network"]
        radio = network.pop("radio", {})
        plane = network.pop("user_plane", {})
        plane.pop("iperf_port", None)
        result["diagnostics"] = {**DIAGNOSTICS, **plane}
        result["selection"] = {**SELECTION, "band": radio.get("band", 78),
                               "pci": radio.get("pci")}
        # Preserve the old reference separately: carrier center is NOT serving SSB.
        result["radio_reference"] = radio
        result["radio_reference"]["tac"] = network.pop("tac", None)
        result["recovery"] = dict(RECOVERY)
        result["schema_version"] = 3
    return result


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid " + label)


DEVICE = {"usb_vendor_id": "2c7c", "usb_product_id": "0801",
          "at_interface_number": "02", "serial_lock": "/var/lib/agentic-ocudu/v2-ue/serial.lock"}


def revision(value):
    public_value = {key: item for key, item in value.items()
                    if key not in {"release", "sim_sha256", "revision"}}
    return hashlib.sha256(json.dumps(public_value, sort_keys=True).encode()).hexdigest()[:16]


def validate(value):
    result = copy.deepcopy(value)
    if result.get("schema_version") != 3 or result.get("name") != "agentic-ocudu-jetson-v2":
        raise ValueError("Unsupported Jetson configuration schema")
    network = result["network"]
    if set(network) != {"plmn", "slice", "data"}:
        raise ValueError("Unknown network access field")
    if not re.fullmatch(r"[0-9]{5,6}", network.get("plmn", "")):
        raise ValueError("Invalid PLMN")
    slice_ = network["slice"]
    if set(slice_) - {"sst", "sd"}:
        raise ValueError("Unknown slice field")
    integer(slice_.get("sst"), 0, 255, "SST")
    if "sd" in slice_ and not re.fullmatch(r"[0-9a-fA-F]{6}", str(slice_["sd"])):
        raise ValueError("Invalid SD")
    data = network["data"]
    if set(data) != set(REFERENCE["data"]):
        raise ValueError("Unknown data field")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,98}[A-Za-z0-9])?", data.get("dnn", "")):
        raise ValueError("Invalid DNN")
    if data.get("pdu_type") != "IP":
        raise ValueError("Only the verified IPv4 PDU path is supported")
    ipaddress.IPv4Network(data["ue_pool"])
    integer(data["qos_5qi"], 1, 255, "5QI")
    integer(data["cid_min"], 1, 16, "minimum CID")
    integer(data["cid_max"], data["cid_min"], 16, "maximum CID")
    policy = result["selection"]
    if set(policy) != set(SELECTION) or policy["rat"] != "NR5G-SA" or policy["mode"] != "observe_only":
        raise ValueError("Only observe-only NR SA selection is supported")
    for key, maximum in (("band", 1024), ("pci", 1007), ("ssb_arfcn", 3279165)):
        if policy[key] is not None:
            integer(policy[key], 1 if key == "band" else 0, maximum, key)
    diagnostics = result["diagnostics"]
    if set(diagnostics) != set(DIAGNOSTICS):
        raise ValueError("Unknown diagnostics field")
    for key in set(DIAGNOSTICS) - {"required"}:
        ipaddress.IPv4Address(diagnostics[key])
    required = diagnostics["required"]
    if not isinstance(required, list) or len(required) < 2 or len(set(required)) != len(required) or set(required) - {"gateway", "upf", "ext_dn", "public"}:
        raise ValueError("At least two distinct bound probes are required")
    recovery = result["recovery"]
    if set(recovery) != set(RECOVERY):
        raise ValueError("Unknown recovery field")
    for key, low, high in (("natural_wait_seconds", 30, 600), ("cooldown_seconds", 300, 3600), ("max_attempts", 1, 3)):
        integer(recovery[key], low, high, key)
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
            "selection": copy.deepcopy(config["selection"]),
            "diagnostics": copy.deepcopy(config["diagnostics"]),
            "radio_reference": copy.deepcopy(config.get("radio_reference", {})),
            "recovery": copy.deepcopy(config["recovery"]),
            "release": config.get("release", "development"),
            "commissioned": config["commissioned"],
            "management_verified": config["management_verified"],
            "sim_fingerprint_configured": bool(config.get("sim_sha256")),
            "route_policy": "Verified cellular IPv4 default with automatic Wi-Fi fallback"}
