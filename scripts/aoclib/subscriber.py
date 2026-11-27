"""Insert one explicitly supplied SIM subscription; never update existing SQN state."""

import json
import os
from pathlib import Path
import re
import subprocess

from .core import write_json


def validate_material(material):
    patterns = {"imsi": r"[0-9]{15}", "ki": r"[0-9a-fA-F]{32}", "opc": r"[0-9a-fA-F]{32}",
                "sqn": r"[0-9a-fA-F]{12}", "amf": r"[0-9a-fA-F]{4}"}
    if not isinstance(material, dict) or set(material) != set(patterns):
        raise ValueError("SIM input must contain exactly imsi, ki, opc, sqn and amf")
    for field, pattern in patterns.items():
        if not isinstance(material[field], str) or not re.fullmatch(pattern, material[field]):
            raise ValueError("Invalid SIM field: " + field)


def sql_text(value):
    # Encode text as a MySQL hex literal, independent of quoting and SQL modes.
    if not isinstance(value, str):
        value = json.dumps(value, separators=(",", ":"))
    return "CONVERT(0x" + value.encode("utf-8").hex() + " USING utf8mb4)"


def statements(config, material):
    validate_material(material)
    radio = config["radio"]
    slice_info = {"sst": radio["sst"]}
    if radio.get("sd") is not None:
        slice_info["sd"] = radio["sd"]
    auth = {"ueid": material["imsi"], "authenticationMethod": "5G_AKA",
            "encPermanentKey": material["ki"], "encOpcKey": material["opc"],
            "sequenceNumber": {"sqn": material["sqn"], "sqnScheme": "NON_TIME_BASED", "lastIndexes": {"ausf": 0}},
            "authenticationManagementField": material["amf"], "algorithmId": "milenage", "supi": material["imsi"]}
    access = {"ueid": material["imsi"], "servingPlmnid": radio["plmn"],
              "subscribedUeAmbr": {"uplink": "500Mbps", "downlink": "1000Mbps"},
              "nssai": {"defaultSingleNssais": [slice_info]}}
    dnns = {dnn: {"pduSessionTypes": {"defaultSessionType": "IPV4", "allowedSessionTypes": ["IPV4"]},
                   "sscModes": {"defaultSscMode": "SSC_MODE_1", "allowedSscModes": ["SSC_MODE_1"]},
                   "5gQosProfile": {"5qi": qi, "arp": {"priorityLevel": 1, "preemptCap": "NOT_PREEMPT",
                                                        "preemptVuln": "NOT_PREEMPTABLE"}},
                   "sessionAmbr": {"uplink": "500Mbps", "downlink": "1000Mbps"}}
            for dnn, qi in (("oai", 9), ("ims", 5))}
    session = {"ueid": material["imsi"], "servingPlmnid": radio["plmn"],
               "singleNssai": slice_info, "dnnConfigurations": dnns}
    lines = ["START TRANSACTION;"]
    for table, row in (("AuthenticationSubscription", auth), ("AccessAndMobilitySubscriptionData", access),
                       ("SessionManagementSubscriptionData", session)):
        lines.append("INSERT INTO `" + table + "` (" + ",".join("`" + key + "`" for key in row) +
                     ") VALUES (" + ",".join(sql_text(value) for value in row.values()) + ");")
    return "\n".join(lines + ["COMMIT;", ""])


def add(config, bundle, source, compose):
    source = Path(source)
    if source.is_symlink():
        raise ValueError("SIM input must not be a symlink")
    stat = source.stat()
    if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise ValueError("SIM input must be private and owned by the invoking user (chmod 600)")
    payload = statements(config, json.loads(source.read_text()))
    command = compose + ["exec", "-T", "mysql", "sh", "-c",
                         'export MYSQL_PWD="$(cat /run/secrets/db_password)"; exec mysql --batch -h 127.0.0.1 -u aoc oai_db']
    result = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=30)
    if result.returncode:
        # MySQL diagnostics can include statement values. Do not echo authentication material.
        raise ValueError("Subscription insert failed; inspect transaction status. Existing subscribers are never overwritten")
    meta = json.loads((bundle / "bundle.json").read_text())
    meta["subscribers_provisioned"] = True
    meta["sqn_resynchronization_verified"] = False
    write_json(bundle / "bundle.json", meta)
