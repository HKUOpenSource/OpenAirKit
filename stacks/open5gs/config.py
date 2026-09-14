"""Validation for the public, single-data-PDU Open5GS profile."""
from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Union


def load(path: Union[str, Path]) -> dict:
    profile = json.loads(Path(path).read_text())
    if profile.get("schema_version") != 1:
        raise ValueError("unsupported network profile schema")
    if profile.get("plmn") != "46003" or profile.get("tac") != 1:
        raise ValueError("unexpected PLMN or TAC")
    if profile.get("slice", {}).get("sst") != 1:
        raise ValueError("unexpected slice")
    data = profile.get("data", {})
    if data.get("dnn") != "oai" or data.get("pdu_type") != "IPv4":
        raise ValueError("V2 requires the single IPv4 oai DNN")
    if ipaddress.ip_network(data.get("ue_pool", ""), strict=True) != ipaddress.ip_network("10.0.0.0/24"):
        raise ValueError("unexpected UE pool")
    if data.get("qos_5qi") != 9:
        raise ValueError("V2 data QoS must be 5QI 9")
    radio = profile.get("radio", {})
    if (radio.get("band"), radio.get("channel_bandwidth_mhz"), radio.get("common_scs_khz"),
            radio.get("carrier_arfcn"), radio.get("pci")) != (78, 20, 30, 643392, 666):
        raise ValueError("radio profile does not match the reviewed first-stage baseline")
    tdd = radio.get("tdd", {})
    if tuple(tdd.get(key) for key in ("period_ms", "downlink_slots", "uplink_slots",
                                      "special_downlink_symbols", "special_uplink_symbols")) != (5, 7, 2, 6, 4):
        raise ValueError("unexpected TDD profile")
    return profile
