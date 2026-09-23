from typing import Literal
"""Unprivileged HTTP API for the independent V2 Jetson console."""
import argparse
import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field


PUBLIC_ENDPOINTS = frozenset({"/api/v1/health", "/api/v1/auth/login"})


def password_record(password):
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return salt + ":" + digest


def password_matches(password, record):
    try:
        salt, digest = record.split(":", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return hmac.compare_digest(actual, digest)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(max_length=256)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["setup", "recover"]
    revision: str
    params: dict = Field(default_factory=dict)


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool


class Maintenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


async def rpc(path, payload):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(path, limit=8 * 1024 * 1024), 2)
        try:
            encoded = json.dumps(payload).encode()
            if len(encoded) > 8192:
                raise ValueError("Request too large")
            writer.write(encoded + b"\n")
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), 15)
            if len(line) > 8 * 1024 * 1024:
                raise ValueError("Executor response too large")
            reply = json.loads(line)
        finally:
            writer.close()
            await writer.wait_closed()
        if not reply.get("ok"):
            raise HTTPException(reply.get("code", 400), reply.get("error", "Executor request failed"))
        return reply["result"]
    except HTTPException:
        raise
    except (OSError, asyncio.TimeoutError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(503, "Device executor unavailable") from error


def redacted(value):
    """Remove device/network identity fields while retaining diagnostic state."""
    if isinstance(value, list):
        return [redacted(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\d.])",
                      "[redacted-ip]", value)
    if not isinstance(value, dict):
        return value
    omitted = {"sim_sha256", "password_hash", "source", "data_address", "wifi_address", "address"}
    return {key: redacted(item) for key, item in value.items() if key not in omitted}


def create_app(config, transport=None):
    app = FastAPI(title="Agentic-OCUDU Jetson V2", docs_url=None, redoc_url=None,
                  openapi_url=None)
    auth = Path(config["web_state_dir"]) / "auth.db"
    auth.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(auth) as database:
        database.execute("CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL)")
    os.chmod(auth, 0o600)
    attempts = {}

    async def call(operation, **kwargs):
        payload = {"op": operation, **kwargs}
        try:
            return await (transport(payload) if transport else rpc(config["agent_socket"], payload))
        except HTTPException:
            raise
        except (ValueError, KeyError) as error:
            code = 409 if type(error).__name__ == "Conflict" else 400
            raise HTTPException(code, str(error)) from error

    def session(request):
        token = request.cookies.get("aoc_v2_jetson_session", "")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(auth) as database:
            row = database.execute("SELECT csrf,expires FROM sessions WHERE token=?", (digest,)).fetchone()
            if row and row[1] <= time.time():
                database.execute("DELETE FROM sessions WHERE token=?", (digest,))
                row = None
        if not row:
            raise HTTPException(401, "Session expired")
        return row

    @app.middleware("http")
    async def protect(request, handler):
        try:
            if request.url.path.startswith("/api/v1/") and request.url.path not in PUBLIC_ENDPOINTS:
                row = session(request)
                if request.method not in {"GET", "HEAD"} and not hmac.compare_digest(
                        request.headers.get("x-csrf-token", ""), row[0]):
                    raise HTTPException(403, "CSRF validation failed")
            if request.method not in {"GET", "HEAD"}:
                origin = request.headers.get("origin")
                if origin and origin != str(request.base_url).rstrip("/"):
                    raise HTTPException(403, "Cross-origin write denied")
            response = await handler(request)
        except HTTPException as error:
            response = JSONResponse({"detail": error.detail}, status_code=error.status_code)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self'; "
                                                       "img-src 'self' data:; connect-src 'self'; "
                                                       "frame-ancestors 'none'; base-uri 'none'")
        return response

    @app.post("/api/v1/auth/login")
    async def login(body: Login, request: Request, response: Response):
        host = request.client.host if request.client else "local"
        recent = [attempt for attempt in attempts.get(host, []) if time.time() - attempt < 60]
        if len(recent) >= 5:
            raise HTTPException(429, "Too many failed login attempts; retry in one minute")
        if not password_matches(body.password, config["password_hash"]):
            attempts[host] = recent + [time.time()]
            raise HTTPException(401, "Invalid password")
        attempts.pop(host, None)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with sqlite3.connect(auth) as database:
            database.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            database.execute("INSERT INTO sessions VALUES(?,?,?)",
                             (hashlib.sha256(token.encode()).hexdigest(), csrf, time.time() + 8 * 3600))
        response.set_cookie("aoc_v2_jetson_session", token, httponly=True, samesite="strict",
                            secure=bool(config.get("secure_cookie")), max_age=8 * 3600)
        return {"csrf": csrf}

    @app.get("/api/v1/auth/session")
    async def auth_session(request: Request):
        return {"csrf": session(request)[0]}

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request, response: Response):
        token = hashlib.sha256(request.cookies.get("aoc_v2_jetson_session", "").encode()).hexdigest()
        with sqlite3.connect(auth) as database:
            database.execute("DELETE FROM sessions WHERE token=?", (token,))
        response.delete_cookie("aoc_v2_jetson_session")
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        try:
            state = await call("status")
            device = state.get("quality", "unknown")
        except HTTPException:
            device = "unavailable"
        return {"status": "ok", "web": "ok", "device": device}

    @app.get("/api/v1/config")
    async def configuration():
        return await call("config")

    @app.get("/api/v1/status")
    async def status():
        return await call("status")

    @app.get("/api/v1/jobs")
    async def jobs(limit: int = 100):
        if not 1 <= limit <= 500:
            raise HTTPException(400, "Invalid task limit")
        return await call("jobs", limit=limit)

    @app.get("/api/v1/jobs/{identifier}")
    async def job(identifier: str):
        return await call("job", id=identifier)

    @app.post("/api/v1/jobs")
    async def create(body: Task):
        return await call("create", **body.model_dump())

    @app.post("/api/v1/jobs/{identifier}/run")
    async def run_job(identifier: str, body: Confirm):
        return await call("run", id=identifier, confirmed=body.confirmed)

    @app.post("/api/v1/jobs/{identifier}/cancel")
    async def cancel_job(identifier: str):
        return await call("cancel", id=identifier)

    @app.post("/api/v1/maintenance")
    async def maintenance(body: Maintenance):
        return await call("maintenance", enabled=body.enabled)

    @app.get("/api/v1/history")
    async def history(hours: int = 24, kind: str = "", level: str = "", before: int = None):
        if not 1 <= hours <= 720:
            raise HTTPException(400, "Invalid history window")
        return await call("history", hours=hours, kind=kind, level=level, before=before)

    @app.get("/api/v1/metrics")
    async def metrics(hours: int = 1):
        if not 1 <= hours <= 168:
            raise HTTPException(400, "Invalid metric window")
        return await call("metrics", hours=hours)

    @app.get("/api/v1/diagnostics")
    async def diagnostics():
        return redacted({"at": time.time(), "version": config.get("release", "development"),
                         "status": await call("status"), "config": await call("config"),
                         "jobs": await call("jobs", limit=100),
                         "events": await call("history", hours=24)})

    @app.get("/api/v1/events/stream")
    async def stream(request: Request):
        started = time.monotonic()

        async def events():
            while not await request.is_disconnected() and time.monotonic() - started < 15:
                try:
                    session(request)
                    yield "event: status\ndata: " + json.dumps(await call("status")) + "\n\n"
                except HTTPException as error:
                    event = "expired" if error.status_code == 401 else "unavailable"
                    yield "event: " + event + "\ndata: {}\n\n"
                    if error.status_code == 401:
                        return
                await asyncio.sleep(2)
            yield "event: reconnect\ndata: {}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no"})

    frontend = Path(config["frontend_dir"]).resolve()
    if (frontend / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}")
    async def page(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown endpoint")
        return FileResponse(frontend / "index.html")

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--port", type=int, default=8878)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    uvicorn.run(create_app(config), host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
