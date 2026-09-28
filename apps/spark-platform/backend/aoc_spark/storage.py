import json
from pathlib import Path
import sqlite3
import time
from datetime import datetime, timezone


class Store:
    SCHEMA_VERSION = 6
    NUMERIC_UNITS = frozenset(('ratio', 'byte', 'bit/s', 'cores', 'C', 'seconds', 'dB', 'count'))

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        version = 0
        if Path(path).exists():
            with self.connect() as existing:
                version = existing.execute("PRAGMA user_version").fetchone()[0]
                if version > self.SCHEMA_VERSION:
                    raise ValueError("Database schema is newer than this monitor release")
                if version < self.SCHEMA_VERSION:
                    with sqlite3.connect(self.path + ".before-v6-" + str(time.time_ns()) + ".db") as backup:
                        existing.backup(backup)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS snapshots(at TEXT PRIMARY KEY, inserted REAL NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, kind TEXT NOT NULL, stack TEXT NOT NULL, at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entity_samples(id TEXT NOT NULL, at TEXT NOT NULL, stack TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(id,at));
                CREATE TABLE IF NOT EXISTS control_tasks(id TEXT PRIMARY KEY, action TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS samples_time ON entity_samples(at);
                CREATE INDEX IF NOT EXISTS events_time ON events(at,id);
                CREATE INDEX IF NOT EXISTS control_time ON control_tasks(updated,id);
                CREATE TABLE IF NOT EXISTS metric_catalog(entity TEXT NOT NULL, name TEXT NOT NULL,
                    unit TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY(entity,name,unit));
            """)
            if version < self.SCHEMA_VERSION:
                # Scan retained samples once during migration, never on page reads.
                db.execute("""INSERT INTO metric_catalog
                    SELECT s.id,json_extract(m.value,'$.name'),COALESCE(json_extract(m.value,'$.unit'),''),MAX(s.at)
                    FROM entity_samples s, json_each(s.body,'$.metrics') m
                    WHERE json_type(m.value,'$.name')='text' AND
                        (json_type(m.value,'$.value') IN ('integer','real') OR
                         json_extract(m.value,'$.unit') IN ('ratio','byte','bit/s','cores','C','seconds','dB','count'))
                    GROUP BY 1,2,3
                    ON CONFLICT(entity,name,unit) DO UPDATE SET last_seen=MAX(last_seen,excluded.last_seen)""")
                db.execute("PRAGMA user_version=6")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def annotate(self, snapshot):
        with self.connect() as db:
            for device in snapshot.get('devices', []):
                row=db.execute('SELECT body FROM entities WHERE id=? AND kind=?',(device['id'],'device')).fetchone()
                first=device.get('first_seen',device['observed_at'])
                if row:
                    previous=json.loads(row[0])
                    first=min(first,previous.get('first_seen',previous['observed_at']))
                device['first_seen']=first
        return snapshot

    def ingest(self, snapshot, retention_days=7, event_retention_days=30):
        snapshot=self.annotate(json.loads(json.dumps(snapshot)))
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (snapshot["observed_at"], time.time(), json.dumps(snapshot)))
            for event in snapshot.get("events", []):
                db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)", (event["id"], event["at"], json.dumps(event)))
            for kind, items in (("device", snapshot.get("devices", [])), ("component", snapshot.get("components", []) + snapshot.get("links", []))):
                for item in items:
                    body = json.dumps(item)
                    db.execute("INSERT INTO entities VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET at=excluded.at,body=excluded.body",
                               (item["id"], kind, item["stack"], snapshot["observed_at"], body))
                    db.execute("INSERT OR IGNORE INTO entity_samples VALUES(?,?,?,?)", (item["id"], snapshot["observed_at"], item["stack"], body))
                    db.executemany("INSERT INTO metric_catalog VALUES(?,?,?,?) "
                                   "ON CONFLICT(entity,name,unit) DO UPDATE SET last_seen=excluded.last_seen "
                                   "WHERE excluded.last_seen>last_seen",
                                   [(item["id"], metric["name"], metric.get("unit") or "", snapshot["observed_at"])
                                    for metric in item.get("metrics", [])
                                    if isinstance(metric.get("name"), str) and
                                    (type(metric.get("value")) in (int, float) or metric.get("unit") in self.NUMERIC_UNITS)])
            db.execute("DELETE FROM snapshots WHERE inserted < ?", (time.time() - retention_days * 86400,))
            db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY at DESC LIMIT 10000)")
            db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            db.execute("DELETE FROM audit WHERE at < ?", (time.time() - event_retention_days * 86400,))
            cutoff = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - retention_days * 86400))
            db.execute("DELETE FROM entity_samples WHERE at < ?", (cutoff,))
            db.execute("DELETE FROM metric_catalog WHERE last_seen < ?", (cutoff,))
            event_cutoff = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - event_retention_days * 86400))
            for table in ("entities", "events"):
                db.execute("DELETE FROM " + table + " WHERE at < ?", (event_cutoff,))
            db.execute("DELETE FROM control_tasks WHERE updated < ? AND state IN ('succeeded','failed','cancelled','interrupted')",
                       (time.time() - event_retention_days * 86400,))

    def history(self, limit):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM snapshots ORDER BY at DESC LIMIT ?", (limit,))][::-1]

    def events(self, limit, stack=None, level=None, entity=None, since=None, until=None, cursor=None, kind=None):
        filters, args = [], []
        for field, value in (("stack", stack), ("level", level), ("entity", entity), ("kind", kind)):
            if value:
                filters.append("json_extract(body, '$." + field + "') = ?")
                args.append(value)
        for op, value in ((">=", since), ("<=", until)):
            if value:
                filters.append("at " + op + " ?")
                args.append(value)
        with self.connect() as db:
            if cursor:
                row = db.execute("SELECT at,id FROM events WHERE id=?", (cursor,)).fetchone()
                if not row:
                    return []
                filters.append("(at,id) < (?,?)")
                args.extend(row)
            where = " WHERE " + " AND ".join(filters) if filters else ""
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM events" + where + " ORDER BY at DESC,id DESC LIMIT ?", (*args, limit))]

    def event_kinds(self, stack=None):
        with self.connect() as db:
            return [row[0] for row in db.execute(
                "SELECT DISTINCT json_extract(body, '$.kind') FROM events "
                "WHERE (? IS NULL OR json_extract(body, '$.stack')=?) ORDER BY 1", (stack, stack)) if row[0]]

    def history_catalog(self, stack=None, after="", limit=200):
        with self.connect() as db:
            rows = list(db.execute(
                "SELECT id,kind,body FROM entities WHERE id>? AND (? IS NULL OR stack=? OR id='spark') "
                "ORDER BY id LIMIT ?", (after, stack, stack, limit + 1)))
            items = []
            # Only retained numeric metric names/units are returned, never raw samples.
            for identifier, kind, body in rows[:limit]:
                entity = json.loads(body)
                metrics = [{"name": name, "unit": unit} for name, unit in db.execute(
                    "SELECT name,unit FROM metric_catalog WHERE entity=? ORDER BY name,unit", (identifier,))]
                items.append({"id": identifier, "name": entity.get("identity", entity.get("name", identifier)),
                              "apiKind": "devices" if kind == "device" else "components", "metrics": metrics})
        return {"items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}

    def entities(self, kind, stack=None, query="", state=None, limit=200):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM entities WHERE kind=? AND (? IS NULL OR stack=?) ORDER BY at DESC LIMIT 1000", (kind, stack, stack))
            items = [json.loads(row[0]) for row in rows]
        return [v for v in items if (not state or v.get("state") == state) and query.lower() in (v.get("identity", v.get("name", "")) + " " + v["id"]).lower()][:limit]

    def entity(self, identifier, kind):
        with self.connect() as db:
            row = db.execute("SELECT body FROM entities WHERE id=? AND kind=?", (identifier, kind)).fetchone()
        return json.loads(row[0]) if row else None

    def metrics(self, identifier, since, until, bucket=60, limit=720):
        # Select the last actual sample per bucket. Missing samples remain gaps; no zero filling.
        with self.connect() as db:
            rows = db.execute("""SELECT at,body FROM (
                SELECT at,body,ROW_NUMBER() OVER(PARTITION BY CAST(strftime('%s',at) AS INTEGER)/? ORDER BY at DESC) AS n
                FROM entity_samples WHERE id=? AND at>=? AND at<=?
                ) WHERE n=1 ORDER BY at DESC LIMIT ?""", (bucket, identifier, since, until, limit))
            return [dict(at=at, **json.loads(body)) for at, body in rows][::-1]

    def audit(self, action, detail):
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,action,detail) VALUES(?,?,?)", (time.time(), action, detail))

    def create_control(self, identifier, action):
        now = time.time()
        body = {"id": identifier, "action": action, "state": "queued", "current_step": None,
                "steps": [], "error": None,
                "created_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                "updated_at": datetime.fromtimestamp(now, timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM control_tasks WHERE state IN ('queued','running','cancel_requested') LIMIT 1").fetchone():
                raise ValueError("operation_in_progress")
            db.execute("INSERT INTO control_tasks VALUES(?,?,?,?,?,?)",
                       (identifier, action, "queued", now, now, json.dumps(body)))
        return body

    def update_control(self, identifier, message):
        now = time.time()
        with self.connect() as db:
            row = db.execute("SELECT body FROM control_tasks WHERE id=?", (identifier,)).fetchone()
            if not row:
                return None
            body = json.loads(row[0])
            step = message.get("step")
            if step:
                body["steps"] = [item for item in body.get("steps", []) if item.get("name") != step.get("name")]
                body["steps"].append(step)
            for key in ("state", "current_step", "error"):
                if key in message:
                    body[key] = message[key]
            body["updated_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
            db.execute("UPDATE control_tasks SET state=?,updated=?,body=? WHERE id=?",
                       (body["state"], now, json.dumps(body), identifier))
            return body

    def control(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT body FROM control_tasks WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def controls(self, limit=50, unfinished=False):
        where = " WHERE state IN ('queued','running','cancel_requested')" if unfinished else ""
        with self.connect() as db:
            rows = db.execute("SELECT body FROM control_tasks" + where + " ORDER BY created DESC LIMIT ?", (limit,))
            return [json.loads(row[0]) for row in rows]

    def backup(self, destination):
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
