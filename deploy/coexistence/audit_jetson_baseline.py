#!/usr/bin/env python3
"""Read-only, site-specific migration audit; never imported by application code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

BASE = "d6801068bb4cc401e2313b31b68495ebb3305b77"
CONFIG_FIELDS = ("expected_plmn", "expected_dnn", "expected_band", "expected_arfcn",
                 "expected_scs", "expected_pci", "rndis_gateway", "upf_address",
                 "ext_dn_address", "public_probe", "speed_server", "demo",
                 "poll_interval", "at_poll_interval", "metrics_interval")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(path):
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Missing regular code directory")
    result = {}
    for item in path.rglob("*"):
        if item.is_symlink():
            raise ValueError("Unexpected code symlink")
        if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
            result[str(item.relative_to(path))] = sha(item)
    return result


def fields(value, names):
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in names if key in value and
            (value[key] is None or isinstance(value[key], (str, bool, int, float)))}


def config_view(config):
    return {key: val for section in config.values() if isinstance(section, dict)
            for key, val in fields(section, CONFIG_FIELDS).items()}


def snapshot_view(value):
    result = fields(value, ("at", "overall", "maintenance"))
    for key, names in {
        "registration": ("stat", "state", "registered", "source"),
        "device": ("usb_interface", "usb_address", "pdu_address", "sim_ready"),
        "data_plane": ("control_plane_ready", "pool_matches", "usable", "upf_reachable", "stale_pdu"),
    }.items():
        result[key] = fields(value.get(key), names)
    result["probes"] = [fields(p, ("address", "ok", "loss", "latency_ms"))
                        for p in value.get("probes", [])[:8]]
    result["radio"] = fields(value.get("radio", {}).get("qeng"),
                             ("state", "rat", "band", "arfcn", "pci", "scs"))
    return result


def database_view(path, now):
    result = {"maintenance": None, "inflight": {}, "samples": []}
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute("SELECT value FROM settings WHERE key='maintenance_mode'").fetchone()
        result["maintenance"] = json.loads(row[0]) if row else None
        for table in ("jobs", "speed_tests"):
            result["inflight"][table] = db.execute("SELECT COUNT(*) FROM " + table +
                " WHERE state IN ('queued','running','cancelling')").fetchone()[0]
        for recorded, snapshot in db.execute("SELECT created_at,snapshot FROM metrics ORDER BY id DESC LIMIT 3"):
            value = snapshot_view(json.loads(snapshot))
            age = now - float(recorded)
            observed = value.get("at")
            observation_fresh = isinstance(observed, (int, float)) and 0 <= now - observed <= 60
            result["samples"].append({"recorded_at": recorded, "age_seconds": age,
                                       "fresh": 0 <= age <= 60 and observation_fresh, "snapshot": value})
    return result


def restoration_view(root, config, helper, state, guard):
    reports = sorted(root.glob("backups/before-original-restore-*/restoration-result.json"))
    if not reports:
        raise ValueError("No completed original restoration report")
    path = reports[-1]
    saved = json.loads(path.read_text())
    original = root / "backups" / saved["original_backup"]
    if original.resolve().parent != (root / "backups").resolve():
        raise ValueError("Invalid recorded backup path")
    evidence = saved["evidence"]
    manifest = json.loads((path.parent / "release.json").read_text())
    checks = {"base_matches": saved.get("base") == BASE and manifest.get("base") == BASE,
              "history_preserved_recorded": saved.get("history_preserved") is True}
    for kind in ("backend", "frontend"):
        checks[kind + "_matches"] = file_map(root / kind) == evidence[kind] == file_map(original / kind)
    package = {k: v for k, v in evidence["backend"].items() if k.startswith("oai_console/")}
    checks["backend_matches_pre_adaptation_manifest"] = package == manifest.get("base_backend")
    checks["config_matches"] = sha(config) == evidence["config_sha256"] == sha(original / "config.toml")
    checks["helper_matches"] = sha(helper) == evidence["helper_sha256"] == sha(original / "helper")
    checks["adaptation_markers_absent"] = not any(p.exists() for p in (
        root / "dual-environment-release.json", state / "environment.json", guard))
    return {"checks": checks, "passed": all(checks.values()), "restored_at": saved.get("restored_at"),
            "original_backup": original.name, "safety_backup": path.parent.name,
            "report_sha256": sha(path), "config_sha256": sha(config), "helper_sha256": sha(helper),
            "backend_sha256": hashlib.sha256(json.dumps(evidence["backend"], sort_keys=True).encode()).hexdigest(),
            "frontend_sha256": hashlib.sha256(json.dumps(evidence["frontend"], sort_keys=True).encode()).hexdigest()}


def command(argv):
    p = subprocess.run(argv, text=True, capture_output=True, timeout=15)
    return {"returncode": p.returncode, "stdout": p.stdout.strip()}


def main():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Run from the Jetson terminal with sudo; no password is stored")
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("Output already exists; use a new output name")
    root, state = Path("/opt/oai-console"), Path("/var/lib/oai-console")
    config, helper = Path("/etc/oai-console/config.toml"), Path("/usr/libexec/oai-console-helper")
    report = {"schema_version": 1, "collected_at": time.time(), "read_only": True, "errors": []}
    try:
        report["restoration"] = restoration_view(root, config, helper, state,
            Path("/etc/systemd/system/oai-console.service.d/90-aoc-jetson-mutual.conf"))
    except (OSError, ValueError, KeyError):
        report["errors"].append("Original restoration evidence is missing, unreadable or inconsistent")
    try:
        report["configuration"] = config_view(tomllib.loads(config.read_text()))
        report["database"] = database_view(state / "console.db", report["collected_at"])
    except (OSError, ValueError, sqlite3.Error):
        report["errors"].append("Configuration or read-only state query failed")
    for key, argv in {
        "services": ["systemctl", "show", "oai-console.service", "aoc-jetson-agent.service", "aoc-jetson-web.service",
                     "-p", "Id", "-p", "ActiveState", "-p", "MainPID", "-p", "UnitFileState"],
        "addresses": ["ip", "-j", "-4", "address", "show"],
        "routes": ["ip", "-j", "-4", "route", "show", "table", "all"],
        "rules": ["ip", "-4", "rule", "show"],
    }.items():
        try:
            report[key] = command(argv)
        except (OSError, subprocess.TimeoutExpired):
            report["errors"].append(key + " query failed")
    # Output is deliberately limited to checksums, public network settings and selected status fields.
    with args.output.open("x") as stream:
        os.fchmod(stream.fileno(), 0o600)
        if "SUDO_UID" in os.environ:
            os.fchown(stream.fileno(), int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print("Read-only baseline report: " + str(args.output))
    print("No AT command, service change or database write was performed.")


if __name__ == "__main__":
    main()
