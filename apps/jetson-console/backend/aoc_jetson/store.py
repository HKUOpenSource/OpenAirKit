import json
from pathlib import Path
import sqlite3
import time
import uuid


SCHEMA_VERSION = 1


class Store:
    """Independent history store. It deliberately has no environment column."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("Unsupported Jetson database version")
            if existed and version == 0:
                backup = self.path.with_name(self.path.name + ".before-schema-1-" + str(time.time_ns()))
                with sqlite3.connect(backup) as target:
                    db.backup(target)
                backup.chmod(0o600)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, updated REAL NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY, at REAL NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS jetson_metrics_at ON metrics(at);
                CREATE INDEX IF NOT EXISTS jetson_events_at ON events(at);
                PRAGMA user_version=1;
            """)

    def connect(self):
        database = sqlite3.connect(self.path, timeout=10)
        database.execute("PRAGMA journal_mode=WAL")
        return database

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def save_job(self, job):
        job["updated_at"] = time.time()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?)",
                       (job["id"], job["updated_at"], json.dumps(job)))
        return job

    def new_job(self, kind, revision, steps, params):
        return self.save_job({"id": uuid.uuid4().hex, "kind": kind, "revision": revision,
                              "state": "ready", "phase": "Review", "created_at": time.time(),
                              "progress": 0, "steps": [{"id": step, "state": "pending"} for step in steps],
                              "params": params, "result": {}, "error": None})

    def jobs(self, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM jobs ORDER BY updated DESC LIMIT ?", (min(limit, 500),)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_job(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise KeyError("Task not found")
        return json.loads(row[0])

    def event(self, kind, message, level="info"):
        with self.connect() as db:
            db.execute("INSERT INTO events(at,kind,level,message) VALUES (?,?,?,?)",
                       (time.time(), kind, level, message[:500]))

    def history(self, hours=24, kind="", level="", before=None):
        with self.connect() as db:
            rows = db.execute("SELECT id,at,kind,level,message FROM events WHERE at>=? AND (?='' OR kind=?) AND (?='' OR level=?) AND id<? ORDER BY id DESC LIMIT 101",
                              (time.time() - hours * 3600, kind, kind, level, level, before or 2**63 - 1)).fetchall()
        return {"items": [dict(zip(("id", "at", "kind", "level", "message"), row)) for row in rows[:100]],
                "next_cursor": rows[99][0] if len(rows) > 100 else None}

    def sample(self, snapshot):
        with self.connect() as db:
            db.execute("INSERT INTO metrics(at,payload) VALUES (?,?)", (snapshot["at"], json.dumps(snapshot)))
            db.execute("DELETE FROM metrics WHERE at<?", (time.time() - 7 * 86400,))
            db.execute("DELETE FROM events WHERE at<?", (time.time() - 30 * 86400,))
            db.execute("DELETE FROM jobs WHERE updated<?", (time.time() - 30 * 86400,))

    def metrics(self, hours=1):
        bucket = max(15, int(hours * 3600 / 360))
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM metrics WHERE id IN (SELECT MAX(id) FROM metrics WHERE at>=? GROUP BY CAST(at/? AS INTEGER)) ORDER BY at",
                              (time.time() - hours * 3600, bucket)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def interrupt(self):
        changed = False
        for job in self.jobs():
            if job["state"] in {"queued", "running", "cancelling", "ready", "paused"}:
                job.update(state="interrupted", error="Device executor restarted; inspect current state before writing")
                self.save_job(job)
                changed = True
        if changed:
            self.set("recovery_paused", True)
        return changed
