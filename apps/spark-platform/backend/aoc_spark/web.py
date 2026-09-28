import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .domain import empty_snapshot, fresh_snapshot, stale_entity
from .storage import Store


REDACTED_DIAGNOSTIC_KEYS = frozenset({
    "address", "b210_holder_pids", "b210_serial", "data_ip", "gateway",
    "identity", "imei", "imsi", "invocation_id", "local_address", "n3_local",
    "n3_remote", "pei", "pid", "radio_pid", "remote_address",
    "source_address", "suci", "supi", "teid",
})


def redacted_diagnostics(value):
    """Return a useful support bundle without device, host, or radio identifiers."""
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if key.casefold() in REDACTED_DIAGNOSTIC_KEYS
                  else redacted_diagnostics(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted_diagnostics(item) for item in value]
    return value


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=256)


class ControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "stop", "restart"]
    confirmation: Literal[True]


def create_app(config):
    store = Store(config["database"])
    auth = json.loads(Path(config["auth_file"]).read_text())
    failures = []
    background = set()
    control_socket = config.get("control_socket", "/run/aoc-control/control.sock")

    def spawn(coroutine):
        task = asyncio.create_task(coroutine)
        background.add(task)
        task.add_done_callback(background.discard)
        return task

    async def control_messages(payload, multiple=False):
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(control_socket), 3)
        writer.write(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        try:
            if multiple:
                while line := await reader.readline():
                    yield json.loads(line)
            else:
                line = await asyncio.wait_for(reader.readline(), 3)
                if not line:
                    raise RuntimeError("executor_closed")
                yield json.loads(line)
        finally:
            writer.close()
            await writer.wait_closed()

    async def query_control(identifier):
        async for message in control_messages({"command": "query", "task_id": identifier}):
            return message
        return {"state": "unknown", "error": "executor_closed"}

    async def poll_control(identifier):
        while True:
            try:
                message = await query_control(identifier)
            except (OSError, RuntimeError, ValueError, asyncio.TimeoutError):
                store.update_control(identifier, {"state": "interrupted", "error": "executor_unavailable"})
                return
            if message.get("state") == "unknown":
                store.update_control(identifier, {"state": "interrupted", "error": "executor_task_unknown"})
                return
            store.update_control(identifier, message)
            if message.get("state") in {"succeeded", "failed", "cancelled"}:
                item = store.control(identifier) or {}
                store.audit("stack_control_result", json.dumps({"task_id": identifier,
                            "action": item.get("action"), "state": message.get("state")}))
                return
            await asyncio.sleep(1)

    async def run_control(identifier, action):
        try:
            async for message in control_messages(
                    {"command": "run", "task_id": identifier, "action": action}, multiple=True):
                if message.get("state") == "conflict":
                    message = {"state": "failed", "error": "operation_in_progress"}
                store.update_control(identifier, message)
                if message.get("state") in {"succeeded", "failed", "cancelled"}:
                    store.audit("stack_control_result", json.dumps({"task_id": identifier,
                                "action": action, "state": message.get("state")}))
                    return
        except (OSError, RuntimeError, ValueError, asyncio.TimeoutError):
            pass
        # Normal EOF is also a lost result when no terminal message arrived.
        # Query the original task; never resend a potentially executed action.
        await poll_control(identifier)

    async def reconcile_controls():
        for item in store.controls(20, unfinished=True):
            spawn(poll_control(item["id"]))

    def snapshot():
        try:
            return fresh_snapshot(store.annotate(json.loads(Path(config["snapshot"]).read_text())))
        except (OSError, ValueError, KeyError, TypeError):
            return empty_snapshot()

    async def ingest():
        while True:
            current = snapshot()
            if current["collector_status"] == "ok":
                await asyncio.to_thread(store.ingest, current, config.get("retention_days", 7),
                                        config.get("event_retention_days", 30))
            await asyncio.sleep(5)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(ingest())
        await reconcile_controls()
        yield
        task.cancel()
        for operation in list(background):
            operation.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.gather(*background, return_exceptions=True)

    app = FastAPI(title="Agentic-OCUDU Spark", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def guard(request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit():
            return Response(status_code=400)
        if int(length) > 4096:
            return Response(status_code=413)
        if request.method not in ("GET", "HEAD"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return Response(status_code=403)
        response = await call_next(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                                 "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"})
        return response

    def session(request, mutation=False):
        token = request.cookies.get("aoc_session", "")
        with store.connect() as db:
            row = db.execute("SELECT csrf, expires FROM sessions WHERE token=?", (token_hash(token),)).fetchone()
        if not row or row[1] < time.time():
            raise HTTPException(401, "login_required")
        if mutation and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), row[0]):
            raise HTTPException(403, "csrf_required")
        return row[0]

    @app.post("/api/v1/login")
    def login(body: Login, response: Response):
        now = time.time()
        failures[:] = [stamp for stamp in failures if stamp > now - 60]
        if len(failures) >= 5:
            raise HTTPException(429, "login_rate_limited")
        if not hmac.compare_digest(password_hash(body.password, auth["salt"]), auth["password_hash"]):
            failures.append(now)
            raise HTTPException(401, "invalid_credentials")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with store.connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (token_hash(token), csrf, now + 8 * 3600))
        response.set_cookie("aoc_session", token, httponly=True, samesite="strict", max_age=8 * 3600,
                            secure=config.get("secure_cookie", False))
        store.audit("login", "success")
        return {"csrf": csrf}

    @app.get("/api/v1/session")
    def current_session(request: Request):
        return {"csrf": session(request)}

    @app.post("/api/v1/logout")
    def logout(request: Request, response: Response):
        session(request, True)
        with store.connect() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (token_hash(request.cookies.get("aoc_session", "")),))
        response.delete_cookie("aoc_session")
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "collector": snapshot()["collector_status"]}

    @app.get("/api/v1/snapshot")
    def current(request: Request):
        session(request)
        return snapshot()

    @app.get("/api/v1/diagnostics")
    def diagnostics(request: Request):
        session(request)
        return redacted_diagnostics(snapshot())

    @app.get("/api/v1/history")
    def history(request: Request, limit: int = Query(120, ge=1, le=720)):
        session(request)
        return {"items": store.history(limit)}

    @app.get("/api/v1/history/catalog")
    def history_catalog(request: Request, stack: Optional[str] = Query(None, pattern="^ocudu$"),
                        after: str = Query("", max_length=100), limit: int = Query(200, ge=1, le=500)):
        session(request)
        snapshot()  # Ingest currently available local evidence before listing retained entities.
        return store.history_catalog(stack, after, limit)

    @app.get("/api/v1/events/kinds")
    def event_kinds(request: Request, stack: Optional[str] = Query(None, pattern="^ocudu$")):
        session(request)
        return {"items": store.event_kinds(stack)}

    @app.get("/api/v1/events")
    def events(request: Request, limit: int = Query(100, ge=1, le=500), stack: Optional[str] = Query(None, pattern="^ocudu$"),
               level: Optional[str] = Query(None, pattern="^(info|warning|error)$"), entity: Optional[str] = Query(None, max_length=100),
               kind: Optional[str] = Query(None, max_length=80), since: Optional[datetime] = None,
               until: Optional[datetime] = None, cursor: Optional[str] = Query(None, max_length=100)):
        session(request)
        start, end = time_range(since, until)
        items = store.events(limit, stack, level, entity, start, end, cursor, kind)
        return {"items": items, "next_cursor": items[-1]["id"] if len(items) == limit else None}

    def time_range(since, until):
        end = until or datetime.now(timezone.utc)
        start = since or end - timedelta(hours=1)
        if until is None and start.tzinfo is not None and timedelta(days=7) < end - start <= timedelta(days=7, seconds=30):
            start = end - timedelta(days=7)
        if start.tzinfo is None or end.tzinfo is None or start > end or end - start > timedelta(days=7):
            raise HTTPException(422, "invalid_time_window")
        return start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()

    @app.get("/api/v1/devices")
    def devices(request: Request, stack: Optional[str] = Query(None, pattern="^ocudu$"), query: str = Query("", max_length=80),
                state: Optional[str] = Query(None, max_length=40), limit: int = Query(200, ge=1, le=500),
                scope: str = Query('subscribers', pattern='^(subscribers|radio|all)$')):
        session(request)
        current = snapshot()
        live = {d["id"]: d for d in current.get("devices", [])}
        saved = store.entities("device", stack, limit=500)
        all_devices = {d["id"]: stale_entity(d) for d in saved}
        all_devices.update(live)
        def matches(d):
            radio = d.get('source') == 'ocudu_scheduler'
            fields = [d['identity'], d['id'], *map(str, d.get('identifiers', {}).values())]
            fields += [str(s.get(k) or '') for s in d.get('sessions', []) for k in ('address', 'dnn', 'id')]
            return ((not stack or d['stack'] == stack) and (scope == 'all' or radio == (scope == 'radio'))
                    and (not state or d.get('state') == state or state == 'stale' and d.get('status') == 'stale')
                    and query.casefold() in ' '.join(fields).casefold())
        return {'items': [d for d in all_devices.values() if matches(d)][:limit]}

    def entity_detail(identifier, kind):
        current = snapshot()
        items = current.get("devices", []) if kind == "device" else current.get("components", []) + current.get("links", [])
        live = next((d for d in items if d["id"] == identifier), None)
        saved = store.entity(identifier, kind)
        if not live and not saved:
            raise HTTPException(404, "entity_not_found")
        return live or stale_entity(saved)

    @app.get("/api/v1/devices/{identifier}")
    def device(request: Request, identifier: str):
        session(request)
        return entity_detail(identifier, "device")

    @app.get("/api/v1/components/{identifier}")
    def component(request: Request, identifier: str):
        session(request)
        return entity_detail(identifier, "component")

    @app.get("/api/v1/devices/{identifier}/metrics")
    @app.get("/api/v1/components/{identifier}/metrics")
    def metrics(request: Request, identifier: str, since: Optional[datetime] = None, until: Optional[datetime] = None,
                bucket: int = Query(60, ge=5, le=3600), limit: int = Query(720, ge=1, le=720)):
        session(request)
        start, end = time_range(since, until)
        return {"items": store.metrics(identifier, start, end, bucket, limit), "aggregation": "last_sample", "bucket_seconds": bucket}

    @app.get("/api/v1/stream")
    async def stream(request: Request):
        session(request)
        async def messages():
            previous = None
            yield 'retry: 1000\n\n'
            try:
                # Keep healthy streams open. Uvicorn's graceful-shutdown timeout
                # bounds service stops without making browsers report false outages.
                while not await request.is_disconnected():
                    try:
                        await asyncio.to_thread(session, request)
                        current = await asyncio.to_thread(snapshot)
                        # A slow read must not publish after logout/session expiry.
                        await asyncio.to_thread(session, request)
                    except HTTPException:
                        yield 'event: auth_expired\ndata: {}\n\n'
                        return
                    version = (current["observed_at"], current["collector_status"])
                    if version != previous:
                        yield 'event: snapshot\ndata: ' + json.dumps(current, allow_nan=False) + '\n\n'
                        previous = version
                    else:
                        yield ': heartbeat\n\n'
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                return
        return StreamingResponse(messages(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.get("/api/v1/audit")
    def audit(request: Request):
        session(request)
        with store.connect() as db:
            return {"items": [dict(at=r[0], action=r[1], detail=r[2]) for r in db.execute("SELECT at,action,detail FROM audit ORDER BY id DESC LIMIT 100")]}

    @app.get("/api/v1/control")
    def controls(request: Request, limit: int = Query(50, ge=1, le=100)):
        session(request)
        return {"items": store.controls(limit)}

    @app.get("/api/v1/control/{identifier}")
    def control(request: Request, identifier: str):
        session(request)
        item = store.control(identifier)
        if not item:
            raise HTTPException(404, "control_task_not_found")
        return item

    @app.post("/api/v1/control")
    async def begin_control(request: Request, body: ControlRequest):
        session(request, True)
        identifier = str(uuid.uuid4())
        try:
            item = store.create_control(identifier, body.action)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        store.audit("stack_control", json.dumps({"task_id": identifier, "action": body.action}))
        spawn(run_control(identifier, body.action))
        return item

    @app.post("/api/v1/control/{identifier}/cancel")
    async def cancel_control(request: Request, identifier: str):
        session(request, True)
        item = store.control(identifier)
        if not item:
            raise HTTPException(404, "control_task_not_found")
        if item["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            raise HTTPException(409, "control_task_already_finished")
        try:
            response = None
            async for message in control_messages({"command": "cancel", "task_id": identifier}):
                response = message
            item = store.update_control(identifier, response or {"state": "interrupted", "error": "executor_closed"})
        except (OSError, RuntimeError, ValueError, asyncio.TimeoutError) as error:
            raise HTTPException(503, "control_executor_unavailable") from error
        store.audit("stack_control_cancel", json.dumps({"task_id": identifier}))
        return item

    frontend = Path(config["frontend"])
    if (frontend / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(frontend / "index.html")

    @app.get("/{page:path}")
    def page(page: str):
        if page.split("/")[0] not in {"overview", "gnb", "ran", "core", "components", "devices", "events", "history", "diagnostics", "operations"}:
            raise HTTPException(404)
        return FileResponse(frontend / "index.html")

    app.state.store = store
    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    uvicorn.run(create_app(config), host="127.0.0.1", port=config.get("port", 8877), proxy_headers=False,
                access_log=False, timeout_graceful_shutdown=10)


if __name__ == "__main__":
    main()
