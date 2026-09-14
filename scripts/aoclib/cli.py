import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts import host_inventory
from scripts.validate import validate
from .core import SERVICES, compose_config, nf_config, prepare, write_json
from .preflight import inspect
from . import subscriber
from . import radio


ROOT = Path(__file__).resolve().parents[2]


def installed(action):
    runtime = Path("/opt/agentic-ocudu/current/scripts/radio_runtime.py")
    if not runtime.is_file():
        raise ValueError("Production radio package is not installed; stage and install it before handoff")
    argv = ["/usr/bin/python3", "-I", str(runtime), action]
    if os.geteuid() != 0:
        argv = ["/usr/bin/sudo", "-n", *argv]
    subprocess.run(argv, check=True)


def inventory(ssh=None):
    if not ssh:
        return host_inventory.collect()
    if ssh.startswith("-") or any(char.isspace() for char in ssh):
        raise ValueError("Invalid SSH target")
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh, "python3 -"],
                            input=(ROOT / "scripts/host_inventory.py").read_text(), text=True,
                            capture_output=True, check=True, timeout=300)
    return json.loads(result.stdout)


def compose_args(config, bundle):
    meta = json.loads((bundle / "bundle.json").read_text())
    if meta["project"] != config["names"]["compose_project"] or meta["project"] != "aoc-cn5g":
        raise ValueError("Bundle project ownership mismatch")
    expected_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if meta.get("config_sha256") != expected_hash:
        raise ValueError("Bundle configuration differs from the selected environment")
    expected = compose_config(config, json.loads((ROOT / "config/images.lock.json").read_text()))
    if json.loads((bundle / "compose.json").read_text()) != expected:
        raise ValueError("Compose differs from the isolated generated definition; regenerate before deploying")
    password = (bundle / "secrets/db_password").read_text()
    if json.loads((bundle / "nf.json").read_text()) != nf_config(config, password):
        raise ValueError("NF configuration differs from the isolated environment")
    return ["docker", "compose", "--project-name", meta["project"],
            "--project-directory", str(bundle), "-f", str(bundle / "compose.json")]


def core_states(argv):
    raw = subprocess.check_output(argv + ["ps", "--all", "--format", "json"], text=True).strip()
    if not raw:
        return []
    return json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]


def core_healthy(states):
    return (len(states) == len(SERVICES) and {item["Service"] for item in states} == set(SERVICES)
            and all(item.get("State") == "running" and item.get("Health") == "healthy" for item in states))


def core_up(config, bundle):
    argv = compose_args(config, bundle)
    # Do not stop existing containers if a new attempt to start additional services fails.
    states = core_states(argv)
    if core_healthy(states):
        return
    if any(item.get("State") == "running" for item in states):
        raise ValueError("Core is partially running or unhealthy; inspect status before changing it")
    try:
        subprocess.run(argv + ["up", "-d", "--wait", "--wait-timeout", "240"], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(argv + ["stop", "--timeout", "30"], check=False)
        raise


def initialize_empty_schema(config, bundle):
    argv = compose_args(config, bundle)
    command = argv + ["exec", "-T", "mysql", "sh", "-c",
                      'export MYSQL_PWD="$(cat /run/secrets/db_password)"; exec mysql -h 127.0.0.1 -u aoc oai_db -N -B']
    count = subprocess.check_output(command, input="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='oai_db';\n",
                                    text=True).strip()
    if count != "0":
        raise ValueError("Schema recovery requires an empty database; existing tables will not be modified")
    subprocess.run(command, input=(bundle / "schema.sql").read_text(), text=True, check=True)


def main():
    parser = argparse.ArgumentParser(description="Independent Agentic-OCUDU deployment tools")
    parser.add_argument("--config", type=Path, default=ROOT / "config/spark.example.json")
    parser.add_argument("--bundle", type=Path, default=ROOT / "local/core")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="Read-only host inventory, without secrets")
    inv.add_argument("--ssh")
    inv.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("preflight", help="Check live or captured resources")
    check.add_argument("--inventory", type=Path)
    check.add_argument("--ssh")
    check.add_argument("--radio", action="store_true")
    prep = sub.add_parser("prepare", help="Generate an empty-subscriber core bundle; does not start services")
    prep.add_argument("--images", type=Path, default=ROOT / "config/images.lock.json")
    prep.add_argument("--schema", type=Path, required=True)
    sub.add_parser("core-up", help="Start only the isolated core/IMS, without touching the radio")
    sub.add_parser("core-stop", help="Stop only the isolated core/IMS; retain volumes")
    sub.add_parser("core-check", help="Require all ten isolated services to be healthy")
    sub.add_parser("core-remove", help="Remove only this project's containers/network, retaining data volumes")
    sub.add_parser("init-empty-schema", help="Recover schema initialization only when the new database has zero tables")
    subscription = sub.add_parser("subscriber-add", help="Insert an explicitly supplied private SIM; never overwrite existing SQN")
    subscription.add_argument("--input", type=Path, required=True)
    staging = sub.add_parser("stage-radio", help="Stage a private production package and run parser checks, without RF")
    staging.add_argument("--build-result", type=Path, required=True)
    staging.add_argument("--probe", type=Path, required=True)
    staging.add_argument("--output", type=Path, required=True)
    sub.add_parser("status")
    sub.add_parser("start", help="Start the installed radio target after preflight")
    sub.add_parser("stop", help="Stop the installed new target and new core")
    sub.add_parser("restore", help="Stop the new radio, then run the original Spark launcher")
    sub.add_parser("radio-preflight", help="Read-only checks before radio handoff; does not open B210")
    sub.add_parser("radio-health", help="Check the running OCUDU process and its AMF association")
    args = parser.parse_args()
    try:
        if args.command in ("radio-preflight", "radio-health"):
            installed("handoff-check" if args.command == "radio-preflight" else "health")
            return 0
        if args.command in ("start", "stop", "restore"):
            if args.command == "start":
                if os.geteuid() == 0:
                    raise ValueError("Run sudo -v, then aocctl start as defaultuser")
                if not Path("/opt/agentic-ocudu/current/scripts/radio_runtime.py").is_file():
                    raise ValueError("Install the production radio package before handoff")
                subprocess.run(["/usr/bin/sudo", "-n", "true"], check=True)
                active = subprocess.run(["systemctl", "is-active", "aoc-stack.target"], capture_output=True, text=True)
                if active.stdout.strip() != "active":
                    # The original launcher takes and releases its own lock before our handoff lock.
                    print("AOC: validating the original recovery entrypoint", flush=True)
                    subprocess.run(["/home/defaultuser/.local/bin/oai-spark-services.sh", "start"], check=True, timeout=360)
            installed(args.command)
            return 0
        if args.command == "status" and Path("/opt/agentic-ocudu/current").exists():
            installed("status")
            return 0
        config = json.loads(args.config.read_text())
        errors = validate(config)
        if errors:
            raise ValueError("; ".join(errors))
        bundle = args.bundle.resolve()
        if args.command == "inventory":
            write_json(args.output, inventory(args.ssh))
            print("Inventory saved: " + str(args.output))
        elif args.command == "preflight":
            captured = json.loads(args.inventory.read_text()) if args.inventory else inventory(args.ssh)
            errors = inspect(config, captured, args.radio)
            if errors:
                raise ValueError("\n".join(errors))
            print("Resource checks passed; this is not an RF or UE acceptance result.")
        elif args.command == "prepare":
            prepare(config, json.loads(args.images.read_text()), bundle, args.schema)
            print("Private bundle generated with no subscribers: " + str(bundle))
        elif args.command == "stage-radio":
            radio.stage(config, bundle, args.build_result.resolve(), args.probe.resolve(), args.output.resolve())
        elif args.command == "core-up":
            errors = inspect(config, inventory())
            if errors:
                raise ValueError("\n".join(errors))
            core_up(config, bundle)
        elif args.command == "core-stop":
            subprocess.run(compose_args(config, bundle) + ["stop", "--timeout", "30"], check=True)
        elif args.command == "core-check":
            if not core_healthy(core_states(compose_args(config, bundle))):
                raise ValueError("Core/IMS readiness check failed")
        elif args.command == "core-remove":
            subprocess.run(compose_args(config, bundle) + ["down", "--timeout", "30"], check=True)
        elif args.command == "init-empty-schema":
            initialize_empty_schema(config, bundle)
        elif args.command == "subscriber-add":
            subscriber.add(config, bundle, args.input, compose_args(config, bundle))
            print("Subscription inserted. UE authentication, dual PDU and SQN resynchronization remain unverified.")
        elif args.command == "status":
            subprocess.run(["systemctl", "--no-pager", "show", "aoc-stack.target", "aoc-core.service", "aoc-gnb.service",
                            "-p", "Id", "-p", "LoadState", "-p", "ActiveState", "-p", "SubState"], check=True)
            if (bundle / "bundle.json").exists():
                subprocess.run(compose_args(config, bundle) + ["ps"], check=True)
        return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
