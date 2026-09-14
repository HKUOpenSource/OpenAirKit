#!/usr/bin/env python3
"""Read only the current test SIM's authentication row into a new private file."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.aoclib.subscriber import validate_material


def export(identity, output):
    if identity.is_symlink() or identity.stat().st_uid != os.getuid() or identity.stat().st_mode & 0o077:
        raise ValueError("SIM identity file must be private and owned by this user")
    source = json.loads(identity.read_text())
    if set(source) != {"imsi"} or not re.fullmatch(r"[0-9]{15}", source["imsi"]):
        raise ValueError("Expected a captured single-SIM identity")
    label = subprocess.check_output(["docker", "inspect", "mysql", "--format",
                                    '{{index .Config.Labels "com.docker.compose.project"}}'], text=True).strip()
    if label != "oai-only-cn5g":
        raise ValueError("Original MySQL container ownership changed")
    query = ("START TRANSACTION READ ONLY; SELECT JSON_OBJECT('imsi',ueid,'ki',encPermanentKey,"
             "'opc',encOpcKey,'sqn',JSON_UNQUOTE(JSON_EXTRACT(sequenceNumber,'$.sqn')),"
             "'amf',authenticationManagementField) FROM AuthenticationSubscription WHERE ueid='" + source["imsi"] +
             "' AND authenticationMethod='5G_AKA' AND algorithmId='milenage'; COMMIT;\n")
    result = subprocess.run(["docker", "exec", "-i", "mysql", "sh", "-c",
                             'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -u root oai_db -N -B'],
                            input=query, text=True, capture_output=True, timeout=30)
    if result.returncode or len(result.stdout.splitlines()) != 1:
        raise ValueError("The targeted read did not return exactly one supported SIM; no material displayed")
    material = json.loads(result.stdout)
    validate_material(material)
    if material["imsi"] != source["imsi"]:
        raise ValueError("Subscriber identity mismatch")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(material, handle)
        handle.write("\n")
    print("One test-SIM authentication record saved privately; old database was read-only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.identity, args.output)
