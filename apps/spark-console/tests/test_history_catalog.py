import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aoc_spark.storage import Store


class HistoryCatalogTests(unittest.TestCase):
    def test_v5_backfill_preserves_retained_names_without_scanning_samples_on_reads(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'history.db'
            store = Store(path)
            now = datetime.now(timezone.utc)
            old = (now - timedelta(days=2)).isoformat()
            latest = now.isoformat()
            entity = dict(id='ocudu:retained', name='Retained device', stack='ocudu', metrics=[])
            with store.connect() as db:
                db.execute('INSERT INTO entities VALUES(?,?,?,?,?)',
                           (entity['id'], 'component', 'ocudu', latest, json.dumps(entity)))
                for at, metrics in ((old, [dict(name='old_metric', value=1, unit='count')]),
                                    (latest, [dict(name='missing', value=None, unit='ratio'),
                                              dict(name='text', value='ok', unit='state')])):
                    db.execute('INSERT INTO entity_samples VALUES(?,?,?,?)',
                               (entity['id'], at, 'ocudu', json.dumps(dict(entity, metrics=metrics))))
                db.execute('DROP TABLE metric_catalog')
                db.execute('PRAGMA user_version=5')
            store = Store(path)
            backups = list(Path(root).glob('*.before-v6-*.db'))
            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 5)
            connect = store.connect

            def catalog_connection():
                db = connect()
                db.set_authorizer(lambda action, table, *_: sqlite3.SQLITE_DENY
                                  if action == sqlite3.SQLITE_READ and table == 'entity_samples'
                                  else sqlite3.SQLITE_OK)
                return db

            with patch.object(store, 'connect', catalog_connection):
                metrics = store.history_catalog('ocudu')['items'][0]['metrics']
            self.assertEqual(metrics, [dict(name='missing', unit='ratio'), dict(name='old_metric', unit='count')])
            Store(path)
            self.assertEqual(len(list(Path(root).glob('*.before-v6-*.db'))), 1)

    def test_ingestion_keeps_latest_metric_presence_and_expires_it_with_samples(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / 'history.db')
            now = datetime.now(timezone.utc)

            def sample(at, metrics):
                return dict(observed_at=at.isoformat(), components=[dict(id='ocudu:retained',
                    name='Retained', stack='ocudu', metrics=metrics)], events=[], devices=[])

            metric = dict(name='signal', value=None, unit='dB')
            store.ingest(sample(now, [metric]))
            store.ingest(sample(now - timedelta(days=2), [metric]))
            store.ingest(sample(now, []))
            self.assertEqual(store.history_catalog()['items'][0]['metrics'], [dict(name='signal', unit='dB')])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT last_seen FROM metric_catalog').fetchone()[0], now.isoformat())
                stale = (now - timedelta(days=8)).isoformat()
                db.execute('UPDATE metric_catalog SET last_seen=?', (stale,))
                db.execute('UPDATE entity_samples SET at=? WHERE at=?', (stale, now.isoformat()))
                db.execute('DELETE FROM entity_samples WHERE at<>?', (stale,))
            store.ingest(dict(observed_at=now.isoformat(), components=[], devices=[], events=[]))
            self.assertEqual(store.history_catalog()['items'][0]['metrics'], [])
