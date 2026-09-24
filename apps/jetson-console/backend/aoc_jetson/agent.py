"""Privileged, single-stack Jetson device coordinator.

The executor owns the serial port and constrained network helper.  It exposes a
small JSON RPC surface over a peer-credential protected Unix socket; it never
accepts AT commands, shell commands, interfaces, targets, profiles or service
names from the web process.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import pwd
import signal
import socket
import struct
import threading
import time

from .config import load, public
from .modem import Modem, active, contexts, select_data
from .network import Network
from .store import Store


TERMINAL = frozenset({"complete", "failed", "cancelled", "interrupted"})
STEPS = {
    "setup": ["Inspect device", "Protect management", "Save baseline",
              "Configure radio", "Register", "Data PDU", "Verify data path", "Prefer 5G"],
    "recover": ["Inspect device", "Protect management", "Verify data path",
                "Reconnect once", "Restore data PDU", "Repair route", "Verify recovery"],
}


class Conflict(ValueError):
    pass


def atomic_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name("." + path.name + "." + str(time.time_ns()))
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def fresh(snapshot, maximum_age=20):
    result = copy.deepcopy(snapshot)
    evidence_at = result.get("evidence_at", result.get("at", 0))
    if time.time() - evidence_at > maximum_age:
        result.update(quality="stale", health="unknown", connected=False,
                      registered=None, data_session_active=None, lab_policy_match=None,
                      management_protected=None, connection_reason="Evidence expired")
        for layer in result.get("layers", []):
            layer.update(state="unknown", quality="stale", reason="Evidence expired")
    return result


class Agent:
    def __init__(self, config, config_path, modem=None, network=None):
        self.config = config
        self.config_path = str(config_path)
        self.store = Store(Path(config["state_dir"]) / "device.db")
        self.modem = modem or Modem(config)
        self.network = network or Network(config, config_path)
        self.maintenance = self.store.setting("maintenance", True)
        self.interrupted = self.store.interrupt()
        self.hardware = threading.RLock()
        self.control = threading.RLock()
        self.cancel = threading.Event()
        self.current = None
        self.worker = None
        self.probes = {}
        self.cached = {"at": 0, "evidence_at": 0, "quality": "unavailable",
                       "health": "unknown", "connected": False, "layers": [],
                       "radio": {}, "data_session": {}, "network": {}, "probes": {}}
        self.last_poll = self.last_sample = self.last_probe = 0
        self.last_probe_evidence = 0
        self.route_good = self.route_bad = 0
        self.evidence_generation = None
        self.outage_since = None

    def status(self):
        value = fresh(self.cached)
        value.update(revision=self.config["revision"], maintenance=self.maintenance,
                     commissioned=bool(self.config.get("commissioned")),
                     management_verified=bool(self.config.get("management_verified")),
                     recovery_paused=self.store.setting("recovery_paused", True),
                     active_job=self.store.get_job(self.current) if self.current else None,
                     simulation=bool(self.config.get("simulation")))
        return value

    def check_cancel(self):
        if self.cancel.is_set():
            raise InterruptedError("Cancelled at a safe operation boundary")

    @staticmethod
    def layer(identifier, name, state, reason, at, quality="ok"):
        return {"id": identifier, "name": name, "state": state, "quality": quality,
                "reason": str(reason)[:240], "at": at}

    def sample(self, probe=False):
        with self.hardware:
            if self.maintenance:
                self.modem.close()
                self.cached = {"at": time.time(), "evidence_at": time.time(), "quality": "ok",
                               "health": "unknown", "connected": False,
                               "connection_reason": "Maintenance mode releases the AT port",
                               "layers": [self.layer("maintenance", "Maintenance", "unknown",
                                                     "AT port released", time.time(), "unavailable")],
                               "radio": {}, "data_session": {}, "network": self.network.snapshot(),
                               "probes": {}, "identity": None, "other_contexts": []}
                return self.cached
            try:
                modem = self.modem.snapshot()
                network = self.network.snapshot()
                generation = (modem.get("registered_5gs"), modem.get("sim_matches"),
                              tuple(modem.get("radio", {}).get(key) for key in
                                    ("plmn", "rat", "band", "pci", "ssb_arfcn")),
                              modem.get("data_session", {}).get("active"),
                              modem.get("data_session", {}).get("address"),
                              network.get("data_interface"), network.get("data_address"))
                if generation != self.evidence_generation:
                    self.probes.clear()
                    self.evidence_generation = generation
                if probe and network.get("quality") == "ok":
                    self.check_cancel()
                    # Independent, interface-bound read-only probes share a sampling
                    # window; serial timeouts must not accumulate before publication.
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        pending = {kind: executor.submit(self.network.probe, kind,
                                                        self.cancel if self.current else None)
                                   for kind in ("gateway", "upf", "ext_dn", "public")}
                        for kind, result in pending.items():
                            self.check_cancel()
                            try:
                                self.probes[kind] = result.result()
                            except Exception as error:
                                self.probes[kind] = {"at": time.time(), "kind": kind,
                                                     "state": "unknown", "reason": str(error)[:240]}
                now = time.time()
                probes = copy.deepcopy(self.probes)
                for value in probes.values():
                    if (now - value.get("at", 0) > 20
                            or value.get("interface") != network.get("data_interface")
                            or value.get("source") != network.get("data_address")):
                        value.update(state="unknown", quality="stale", reason="Probe evidence expired")
                registered = modem.get("registered_5gs") if modem.get("c5greg") is not None else None
                radio = modem.get("radio", {})
                expected = self.config["network"]
                radio_ok = radio.get("rat") == "NR5G-SA" and radio.get("plmn") == expected["plmn"]
                policy_ok = self.policy_matches(radio)
                session = modem.get("data_session", {})
                session_ok = all((session.get("configured"), session.get("active"),
                                  session.get("pool_valid")))
                network_ok = network.get("quality") == "ok" and bool(network.get("data_address"))
                layers = [
                    self.layer("sim", "Modem & SIM", "ok" if modem.get("sim_ready") and modem.get("sim_matches") else "failed",
                               modem.get("identity") or "SIM evidence unavailable", modem["at"]),
                    self.layer("radio", "5G radio", "ok" if radio_ok else "failed",
                               "NR5G-SA / n{} / PCI {}".format(radio.get("band", "--"), radio.get("pci", "--")), modem["at"]),
                    self.layer("registration", "5GS registration", "unknown" if registered is None else "ok" if registered else "failed",
                               "C5GREG unavailable" if registered is None else "C5GREG registered" if registered else "C5GREG not registered", modem["at"]),
                    self.layer("data_pdu", "Data PDU", "ok" if session_ok else "failed",
                               session.get("address") or "No valid data address", session.get("at", modem["at"])),
                    self.layer("rndis", "RNDIS", "ok" if network_ok else "unknown",
                               network.get("data_interface") or network.get("reason", "RNDIS unavailable"), network.get("at", now),
                               "ok" if network_ok else network.get("quality", "unavailable")),
                ]
                for identifier, name in (("gateway", "Modem gateway"), ("upf", "UPF path"),
                                         ("ext_dn", "Data network"), ("public", "Internet")):
                    evidence = probes.get(identifier, {})
                    detail = evidence.get("reason") or ("{} ms".format(evidence["latency_ms"])
                                                        if evidence.get("latency_ms") is not None else "Not measured")
                    layers.append(self.layer(identifier, name, evidence.get("state", "unknown"), detail,
                                             evidence.get("at", 0), evidence.get("quality", "ok")))
                layers.extend([
                    self.layer("lab_policy", "Lab selection policy", "ok" if policy_ok else "failed",
                               "Observed match; no modem lock programmed" if policy_ok else "Serving cell does not match lab policy", modem["at"]),
                    self.layer("management", "Protected management", "ok" if network.get("management_protected") else "failed",
                               network.get("management_reason", "Management route verified"), network.get("at", now))])
                required = {"sim", "radio", "registration", "data_pdu", "rndis", *self.config["diagnostics"]["required"]}
                for item in layers:
                    if now - item["at"] > 20:
                        item.update(state="unknown", quality="stale", reason="Evidence expired")
                connected = all(item["state"] == "ok" for item in layers if item["id"] in required)
                failed = [item["name"] for item in layers if item["id"] in required and item["state"] == "failed"]
                unknown = [item["name"] for item in layers if item["id"] in required and item["state"] == "unknown"]
                health = "ok" if connected else "failed" if failed else "unknown"
                reason = "Registration, session and RNDIS-bound data path verified" if connected else \
                    ("Failed: " + ", ".join(failed) if failed else "Awaiting current evidence: " + ", ".join(unknown))
                self.cached = {"at": now, "evidence_at": min(modem["at"], network.get("at", now)),
                               "quality": "ok", "health": health, "connected": connected,
                               "connection_reason": reason, "layers": layers,
                               "registered": registered,
                               "data_session_active": session_ok, "lab_policy_match": policy_ok,
                               "management_protected": bool(network.get("management_protected")),
                               "identity": modem.get("identity"), "firmware": modem.get("firmware"),
                               "radio": radio, "data_session": session,
                               "other_contexts": modem.get("other_contexts", []),
                               "registration": {key: modem.get(key) for key in
                                                ("registered_5gs", "c5greg", "cereg", "source", "disagrees_with_cereg")},
                               "network": network, "probes": probes,
                               "query_quality": modem.get("query_quality", {})}
                return self.cached
            except Exception as error:
                self.modem.close()
                self.cached = {"at": time.time(), "evidence_at": time.time(),
                               "quality": "unavailable", "health": "unknown", "connected": False,
                               "connection_reason": str(error)[:300],
                               "layers": [self.layer("modem", "Modem evidence", "unknown", error,
                                                     time.time(), "unavailable")],
                               "radio": {}, "data_session": {}, "other_contexts": [],
                               "network": self.network.snapshot(), "probes": {}, "identity": None}
                return self.cached

    def write(self, operation, cid=None):
        self.check_cancel()
        with self.hardware:
            if not self.network.snapshot().get("management_protected"):
                raise Conflict("Current management protection is required for modem writes")
            radio = self.cached.get("radio", {})
            if radio.get("plmn") and not self.policy_matches(radio):
                raise Conflict("Observed serving cell differs from lab policy")
            self.probes.clear()
            return self.modem.write(operation, cid)

    def baseline(self):
        path = Path(self.config["state_dir"]) / "modem-baseline.json"
        with self.hardware:
            fingerprint, _identity = self.modem.fingerprint()
            if fingerprint != self.config.get("sim_sha256"):
                raise ValueError("SIM identity mismatch")
            if path.exists():
                saved = json.loads(path.read_text())
                if saved.get("sim_sha256") != fingerprint:
                    raise ValueError("Baseline belongs to another SIM")
                return saved
            current = contexts(self.modem.query("AT+CGDCONT?"))
            saved = {"schema_version": 1, "sim_sha256": fingerprint,
                     "contexts": {str(key): value for key, value in current.items()},
                     "active": sorted(active(self.modem.query("AT+CGACT?"))), "at": time.time()}
            atomic_private(path, saved)
            return saved

    def wait_for(self, predicate, timeout):
        deadline = time.monotonic() + timeout
        while True:
            self.check_cancel()
            value = self.sample(False)
            if predicate(value):
                return value
            if time.monotonic() >= deadline:
                raise TimeoutError("Verification deadline exceeded")
            if self.cancel.wait(.02 if self.config.get("simulation") else 2):
                self.check_cancel()

    def ensure_data(self):
        definition = self.config["network"]["data"]
        with self.hardware:
            current = contexts(self.modem.query("AT+CGDCONT?"))
            cid, create = select_data(current, definition)
            enabled = active(self.modem.query("AT+CGACT?"))
        if not create and current[cid]["type"] != definition["pdu_type"]:
            if cid in enabled:
                self.write("deactivate", cid)
                enabled.discard(cid)
            self.write("context", cid)
        elif create:
            self.write("context", cid)
        if cid not in enabled:
            self.write("activate", cid)
        return self.wait_for(lambda value: value.get("data_session", {}).get("pool_valid")
                            and value["data_session"].get("active"), 45)

    def create(self, kind, revision, params=None):
        with self.control:
            if revision != self.config["revision"]:
                raise Conflict("Configuration changed; refresh before continuing")
            if kind not in STEPS:
                raise ValueError("Unknown operation")
            if not self.config.get("commissioned") or not self.config.get("management_verified"):
                raise Conflict("Commissioning and management-route verification are required")
            if self.current:
                raise Conflict("An operation is already active")
            if self.maintenance:
                raise Conflict("Exit maintenance before starting an operation")
            params = params or {}
            allowed = {"mode"} if kind == "setup" else set()
            if set(params) - allowed:
                raise ValueError("Unknown task parameter")
            if params.get("mode", "automatic") not in {"automatic", "manual"}:
                raise ValueError("Invalid setup mode")
            job = self.store.new_job(kind, revision, STEPS[kind], params)
            self.current = job["id"]
            self.cancel.clear()
            self.store.event(kind, "Task prepared")
            return job

    def launch(self, identifier, confirmed):
        with self.control:
            if identifier != self.current or self.worker and self.worker.is_alive():
                raise Conflict("Task is not ready")
            job = self.store.get_job(identifier)
            if job["kind"] not in STEPS:
                raise ValueError("Retired task cannot be executed")
            if job["revision"] != self.config["revision"]:
                raise Conflict("Configuration changed")
            if confirmed is not True:
                raise ValueError("Confirm interruption before applying the plan")
            if job["state"] not in {"ready", "paused"}:
                raise Conflict("Task cannot be started")
            self.worker = threading.Thread(target=self.execute, args=(job,), daemon=False)
            self.worker.start()
            return job

    def complete_step(self, job, step):
        step.update(state="complete", finished_at=time.time())
        job["progress"] = round(100 * sum(value["state"] == "complete" for value in job["steps"])
                                / len(job["steps"]))
        self.store.save_job(job)

    def verify_data(self, require_two=False):
        attempts = 2 if require_two else 1
        value = None
        for index in range(attempts):
            value = self.sample(True)
            if not value.get("connected"):
                raise ValueError(value.get("connection_reason", "Data path is not verified"))
            if index + 1 < attempts and self.cancel.wait(.02 if self.config.get("simulation") else 2):
                self.check_cancel()
        return value

    def execute(self, job):
        self.store.set("recovery_paused", True)
        reconnect_used = False
        try:
            if job["kind"] not in STEPS or [step["id"] for step in job["steps"]] != STEPS[job["kind"]]:
                raise ValueError("Retired or invalid task cannot be executed")
            pending = [step for step in job["steps"] if step["state"] == "pending"]
            if job["kind"] == "setup" and job["params"].get("mode") == "manual":
                pending = pending[:1]
            for step in pending:
                self.check_cancel()
                job.update(state="running", phase=step["id"])
                step.update(state="running", at=time.time())
                self.store.save_job(job)
                name = step["id"]
                if name == "Inspect device":
                    value = self.sample(False)
                    if value["quality"] != "ok" or not value.get("identity"):
                        raise ValueError("Current device evidence is unavailable")
                elif name == "Protect management":
                    job["result"]["management"] = self.network.action("protect", self.cancel)
                elif name == "Save baseline":
                    self.baseline()
                elif name == "Configure radio":
                    value = self.sample(False)
                    radio = value.get("radio", {})
                    if radio and radio.get("plmn") and not self.policy_matches(radio):
                        raise ValueError("Serving cell differs from lab policy; observation does not program a modem lock")
                    job["result"]["radio_configuration"] = {
                        "state": "preserved", "mutations": 0,
                        "evidence": {key: radio.get(key) for key in
                                     ("rat", "plmn", "band", "pci", "ssb_arfcn")},
                        "reason": "Current NR SA serving-cell evidence already matches the target"}
                elif name == "Register":
                    value = self.sample(False)
                    if not value.get("registration", {}).get("registered_5gs"):
                        last = self.store.setting("last_reset", 0)
                        if time.time() - last < 300:
                            raise Conflict("Modem reconnect is cooling down")
                        self.store.set("last_reset", time.time())
                        self.write("cfun0")
                        with self.hardware:
                            self.modem.write("cfun1")
                        reconnect_used = True
                        self.wait_for(lambda item: item.get("registration", {}).get("registered_5gs"), 120)
                elif name in {"Data PDU", "Restore data PDU"}:
                    value = self.sample(False)
                    if value.get("registered"):
                        self.ensure_data()
                elif name in {"Verify data path", "Verify recovery"}:
                    if name == "Verify data path" and job["kind"] == "recover":
                        value = self.sample(True)
                        job["result"]["initial_verification"] = {
                            "connected": value.get("connected", False),
                            "reason": value.get("connection_reason"), "at": value.get("at")}
                    else:
                        job["result"]["verification"] = self.verify_data(
                            require_two=name == "Verify recovery")
                elif name == "Prefer 5G":
                    job["result"]["routing"] = self.network.action("promote", self.cancel)
                elif name == "Repair route":
                    job["result"]["route_repair"] = self.network.action("prepare", self.cancel)
                elif name == "Reconnect once":
                    value = self.sample(True)
                    if not value.get("registered") or not value.get("data_session_active"):
                        last = self.store.setting("last_reset", 0)
                        if reconnect_used or time.time() - last < 300:
                            raise Conflict("One reconnect per task and the 300-second cooldown are enforced")
                        self.store.set("last_reset", time.time())
                        self.write("cfun0")
                        with self.hardware:
                            self.modem.write("cfun1")
                        reconnect_used = True
                        self.wait_for(lambda item: item.get("registered"), 120)
                        self.ensure_data()
                self.complete_step(job, step)
            complete = all(step["state"] in {"complete", "skipped"} for step in job["steps"])
            job.update(state="complete" if complete else "paused",
                       phase="Complete" if complete else "Awaiting next step")
            if complete:
                job["progress"] = 100
                self.store.set("recovery_paused", False)
        except Exception as error:
            state = "cancelled" if self.cancel.is_set() else "failed"
            job.update(state=state, error=str(error)[:500])
            for step in job["steps"]:
                if step["state"] == "running":
                    step.update(state=state, error=job["error"])
            try:
                job["cleanup"] = self.network.action("fallback")
            except Exception as cleanup:
                job["cleanup"] = {"state": "unknown", "error": str(cleanup)[:300]}
            self.store.set("recovery_paused", self.cancel.is_set() or not job.get("automatic", False))
        finally:
            with self.control:
                self.store.save_job(job)
                self.store.event(job["kind"], job["state"] + ": " + (job.get("error") or job["phase"]),
                                 "error" if job["state"] == "failed" else "info")
                if job["state"] in TERMINAL:
                    self.current = None
                    # Cancellation belongs to this completed task. Keeping it
                    # set would make later background probes cancel themselves
                    # and incorrectly downgrade device quality to unavailable.
                    self.cancel.clear()

    def cancel_job(self, identifier):
        with self.control:
            job = self.store.get_job(identifier)
            if identifier != self.current:
                return job
            self.cancel.set()
            self.store.set("recovery_paused", True)
            if self.worker and self.worker.is_alive():
                job.update(state="cancelling")
            else:
                job.update(state="cancelled")
                self.current = None
            return self.store.save_job(job)

    def set_maintenance(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Boolean required")
        with self.control:
            if self.current:
                raise Conflict("Cancel the active operation and wait for it to finish")
            with self.hardware:
                self.maintenance = enabled
                self.modem.close()
                self.probes.clear()
                self.store.set("maintenance", enabled)
                self.store.set("recovery_paused", True)
                self.store.event("maintenance", "AT port released" if enabled else "Serial ownership resumed")
            return {"enabled": enabled}

    def policy_matches(self, radio):
        policy = self.config["selection"]
        return (radio.get("rat") == policy["rat"]
                and radio.get("plmn") == self.config["network"]["plmn"]
                and all(policy[key] is None or radio.get(key) == policy[key]
                        for key in ("band", "pci", "ssb_arfcn")))

    def auto_reconcile(self):
        if self.current or self.maintenance or self.store.setting("recovery_paused", True):
            return
        value = self.status()
        if value.get("quality") != "ok" or value.get("registered") is None:
            return
        now = time.time()
        if value.get("registered") and value.get("data_session_active"):
            self.outage_since = None
            # Reset a bounded outage budget only after sustained healthy data evidence.
            if value.get("connected"):
                healthy = self.store.setting("healthy_since", now)
                self.store.set("healthy_since", healthy)
                if now - healthy >= self.config["recovery"]["cooldown_seconds"]:
                    self.store.set("auto_attempts", 0)
            else:
                self.store.set("healthy_since", now)
            return
        self.store.set("healthy_since", now)
        self.outage_since = self.outage_since or now
        policy = self.config["recovery"]
        if now - self.outage_since < policy["natural_wait_seconds"]:
            return
        if not value.get("management_protected") or not self.config.get("commissioned"):
            return
        if now - self.store.setting("last_auto_attempt", 0) < policy["cooldown_seconds"]:
            return
        attempts = self.store.setting("auto_attempts", 0)
        if attempts >= policy["max_attempts"]:
            self.store.set("recovery_paused", True)
            self.store.event("recover", "Automatic recovery limit reached; inspect the network", "warning")
            return
        self.store.set("auto_attempts", attempts + 1)
        self.store.set("last_auto_attempt", now)
        job = self.create("recover", self.config["revision"])
        job["automatic"] = True
        self.store.save_job(job)
        self.launch(job["id"], True)

    def dispatch(self, request):
        if not isinstance(request, dict):
            raise ValueError("Object required")
        op = request.get("op")
        hours = request.get("hours", 1)
        if type(hours) is not int or not 1 <= hours <= 720:
            raise ValueError("Invalid time window")
        if op == "status":
            return self.status()
        if op == "config":
            return public(self.config)
        if op == "jobs":
            return self.store.jobs(request.get("limit", 100))
        if op == "job":
            return self.store.get_job(request["id"])
        if op == "history":
            return self.store.history(request.get("hours", 24), request.get("kind", ""),
                                      request.get("level", ""), request.get("before"))
        if op == "metrics":
            return self.store.metrics(hours)
        if op == "create":
            return self.create(request["kind"], request["revision"], request.get("params"))
        if op == "run":
            return self.launch(request["id"], request.get("confirmed"))
        if op == "cancel":
            return self.cancel_job(request["id"])
        if op == "maintenance":
            return self.set_maintenance(request["enabled"])
        raise ValueError("Unknown executor operation")

    async def serve(self):
        path = Path(self.config["agent_socket"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(str(path))
            except ConnectionRefusedError:
                if path.stat().st_uid != os.getuid():
                    raise PermissionError("Socket belongs to another user")
                path.unlink()
            else:
                raise ValueError("Executor already running")
            finally:
                probe.close()
        web_uid = os.getuid() if self.config.get("simulation") else pwd.getpwnam("aoc-v2-jetson-web").pw_uid

        async def client(reader, writer):
            try:
                peer_socket = writer.get_extra_info("socket")
                if hasattr(socket, "SO_PEERCRED"):
                    peer = struct.unpack("3i", peer_socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    if peer not in {0, web_uid}:
                        raise PermissionError("Peer is not authorized")
                elif not self.config.get("simulation"):
                    raise PermissionError("Peer credential validation unavailable")
                line = await asyncio.wait_for(reader.readline(), 3)
                if len(line) > 8192:
                    raise ValueError("Request too large")
                result = await asyncio.to_thread(self.dispatch, json.loads(line))
                response = {"ok": True, "result": result}
            except Exception as error:
                response = {"ok": False, "error": str(error)[:500],
                            "code": 409 if isinstance(error, Conflict) else 400}
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_unix_server(client, path=str(path), limit=8193)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stop.set)
        os.chmod(path, 0o660)
        if not self.config.get("simulation"):
            import grp
            os.chown(path, 0, grp.getgrnam("aoc-v2-jetson-web").gr_gid)
        try:
            async with server:
                while not stop.is_set():
                    now = time.time()
                    if not self.current and now - self.last_poll >= 10:
                        do_probe = now - self.last_probe >= 10
                        await asyncio.to_thread(self.sample, do_probe)
                        self.last_poll = now
                        if do_probe:
                            self.last_probe = now
                        try:
                            await asyncio.to_thread(self.auto_reconcile)
                        except Exception as error:
                            self.store.set("recovery_paused", True)
                            self.store.event("recovery", str(error)[:250], "warning")
                    if now - self.last_sample >= 15:
                        self.store.sample(self.status())
                        self.last_sample = now
                    try:
                        await asyncio.wait_for(stop.wait(), 2)
                    except asyncio.TimeoutError:
                        pass
        finally:
            self.cancel.set()
            self.store.set("recovery_paused", True)
            if self.worker:
                await asyncio.to_thread(self.worker.join, 50)
            self.modem.close()
            path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = load(args.config)
    if config.get("simulation"):
        if os.geteuid() == 0:
            raise ValueError("Simulation cannot run as root")
        from .simulator import SimModem, SimNetwork
        agent = Agent(config, args.config, SimModem(), SimNetwork())
    else:
        agent = Agent(config, args.config)
    asyncio.run(agent.serve())


if __name__ == "__main__":
    main()
