#!/usr/bin/env python3
"""Exercise subscription inserts in the new database with rollback-only synthetic data."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.aoclib.cli import compose_args
from scripts.aoclib.subscriber import statements


def check(config, bundle):
    argv = compose_args(config, bundle) + ["exec", "-T", "mysql", "sh", "-c",
        'export MYSQL_PWD="$(cat /run/secrets/db_password)"; exec mysql --batch -N -h 127.0.0.1 -u aoc oai_db']

    def query(sql):
        return subprocess.run(argv, input=sql, text=True, capture_output=True, timeout=20)

    material = {"imsi": "001010000000001", "ki": "0" * 32, "opc": "1" * 32, "sqn": "0" * 12, "amf": "8000"}
    count = "SELECT COUNT(*) FROM AuthenticationSubscription WHERE ueid='001010000000001';\n"
    before = query(count)
    if before.returncode or before.stdout.strip() != "0":
        raise ValueError("Synthetic test identity must not already exist")
    sql = statements(config, material)
    assert sql.endswith("COMMIT;\n")
    transaction = sql[:-len("COMMIT;\n")]
    values = query(transaction + "SELECT JSON_EXTRACT(dnnConfigurations, '$.ims.\"5gQosProfile\".\"5qi\"'), "
                   "JSON_EXTRACT(dnnConfigurations, '$.oai.\"5gQosProfile\".\"5qi\"') "
                   "FROM SessionManagementSubscriptionData WHERE ueid='001010000000001';\nROLLBACK;\n")
    if values.returncode or values.stdout.strip() != "5\t9":
        raise ValueError("Subscription schema/QoS transaction check failed")
    # A duplicate inside the same transaction must abort, without committing its first insert.
    inserts = transaction.removeprefix("START TRANSACTION;\n")
    duplicate = query(transaction + inserts + "COMMIT;\n")
    if duplicate.returncode == 0:
        raise ValueError("Duplicate subscription unexpectedly succeeded")
    after = query(count)
    if after.returncode or after.stdout.strip() != "0":
        raise ValueError("Synthetic subscription was not rolled back")
    print(json.dumps({"schema_insert": True, "qos": {"oai": 9, "ims": 5},
                      "duplicate_rejected": True, "synthetic_rows_remaining": 0, "real_sim_verified": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    check(json.loads(args.config.read_text()), args.bundle.resolve())
