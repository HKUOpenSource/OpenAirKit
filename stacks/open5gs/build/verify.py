#!/usr/bin/env python3
"""Run bounded, disposable ARM64 checks without RF, subscriptions or host ports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from prepare import load_lock


def run(args, timeout=60):
    return subprocess.run(args, text=True, capture_output=True, check=True, timeout=timeout).stdout


def inspect(reference):
    item = json.loads(run(["docker", "image", "inspect", reference]))[0]
    if item["Architecture"] != "arm64" or item["Os"] != "linux":
        raise ValueError("Expected a native Linux ARM64 image")
    return {key: item.get(key) for key in ("Id", "Architecture", "Os", "RepoDigests")}


def capture_logs(name, destination):
    process = subprocess.run(["docker", "logs", name], text=True, capture_output=True,
                             check=True, timeout=30)
    (destination / (name + ".stderr.log")).write_text(process.stderr)
    return process.stdout


def verify_unit_suites(tests):
    expected = {"open5gs:unit / " + name for name in ("core", "crypt", "unit")}
    if len(tests) != 3 or {item.get("name") for item in tests} != expected or any(
            item.get("result") != "OK" for item in tests):
        raise ValueError("Incomplete or failing upstream unit suites")
    return [{"name": item["name"], "result": item["result"]} for item in tests]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Evidence directory exists; choose a new directory")
    lock_path = Path(__file__).resolve().parents[1] / "sources.lock.json"
    lock = load_lock(lock_path)
    core = inspect(args.image)
    mongo = inspect(lock["images"]["mongodb"]["reference"])
    args.output.mkdir(parents=True, mode=0o700)
    result = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "source_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
              "open5gs": core, "mongodb": mongo, "passed": False,
              "scope": "build-and-no-rf-smoke-only", "containers": [], "cleanup": {}}
    label = "org.agentic-ocudu.purpose=version-verification"
    resources = ["--network", "none", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
                 "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--label", label]
    names = []
    try:
        name = "aoc-v2-nf-check-" + uuid.uuid4().hex[:12]
        run(["docker", "create", "--name", name, *resources, core["Id"]])
        names.append(name)
        run(["docker", "start", name])
        code = run(["docker", "wait", name], timeout=180).strip()
        logs = capture_logs(name, args.output)
        (args.output / "nf-smoke.json").write_text(logs)
        smoke = json.loads(logs)
        if code != "0" or not smoke["passed"]:
            raise ValueError("NF smoke or clean shutdown failed")
        run(["docker", "cp", name + ":/opt/aoc-evidence/sources.lock.json", str(args.output / "sources.lock.json")])
        if (args.output / "sources.lock.json").read_bytes() != lock_path.read_bytes():
            raise ValueError("Image was not built from the selected source lock")
        for filename in ("packages.tsv", "unit-tests.jsonl"):
            run(["docker", "cp", name + ":/opt/aoc-evidence/" + filename, str(args.output / filename)])
        tests = [json.loads(line) for line in (args.output / "unit-tests.jsonl").read_text().splitlines() if line]
        result["unit_suites"] = verify_unit_suites(tests)
        version = smoke["version"]
        if version != "Open5GS v" + lock["open5gs_version"]:
            raise ValueError("Unexpected Open5GS runtime version")
        result["open5gs"]["version"] = version
        name = "aoc-v2-mongo-check-" + uuid.uuid4().hex[:12]
        run(["docker", "create", "--name", name, *resources, "--user", "mongodb",
             "--tmpfs", "/data/db:rw,size=512m,mode=1777", "--tmpfs", "/data/configdb:rw,size=64m,mode=1777",
             "--entrypoint", "mongod", mongo["Id"], "--bind_ip", "127.0.0.1",
             "--wiredTigerCacheSizeGB", "0.25"])
        names.append(name)
        run(["docker", "start", name])
        deadline = time.monotonic() + 45
        while True:
            try:
                query = 'const d=db.getSiblingDB("aoc_build_smoke"); d.probe.insertOne({n:1}); '
                query += 'if(d.probe.countDocuments({n:1})<1) quit(2); d.dropDatabase(); '
                query += 'print(JSON.stringify({version:db.version(),ping:db.adminCommand({ping:1}).ok}));'
                check = json.loads(run(["docker", "exec", name, "mongosh", "--quiet", "--eval", query], timeout=10))
                if check != {"version": lock["images"]["mongodb"]["version"], "ping": 1}:
                    raise ValueError("Unexpected MongoDB response/version")
                result["mongodb"].update(check)
                break
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        result["passed"] = True
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)[:500]
    finally:
        result["containers"] = names
        for name in reversed(names):
            try:
                run(["docker", "stop", "--time", "20", name], timeout=30)
                state = json.loads(run(["docker", "inspect", name]))[0]["State"]
                clean = not state["Running"] and state["ExitCode"] == 0 and not state["OOMKilled"]
                result["cleanup"][name] = {"clean_exit": clean, "exit_code": state["ExitCode"]}
                if not clean:
                    result["passed"] = False
                    (args.output / (name + ".log")).write_text(capture_logs(name, args.output))
                run(["docker", "rm", "-v", name])
                result["cleanup"][name]["removed"] = True
            except Exception as exc:
                result["passed"] = False
                result["cleanup"][name] = {"error": str(exc)[:500]}
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        result["artifact_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in args.output.iterdir() if p.is_file()}
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
