import asyncio
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from aoc_spark.domain import empty_snapshot
from aoc_spark.web import create_app, token_hash


class LiveStreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        (root / 'auth.json').write_text(json.dumps(dict(salt='00' * 16, password_hash='unused')))
        (root / 'snapshot.json').write_text(json.dumps(empty_snapshot()))
        self.app = create_app(dict(auth_file=str(root / 'auth.json'), database=str(root / 'history.db'),
                                  snapshot=str(root / 'snapshot.json'), frontend=str(root)))
        self.store = self.app.state.store
        with self.store.connect() as db:
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash('synthetic-session'), 'csrf', time.time()+3600))
        self.request = SimpleNamespace(cookies={'aoc_session': 'synthetic-session'},
                                       is_disconnected=AsyncMock(return_value=False))
        self.endpoint = next(route.endpoint for route in self.app.routes
                             if getattr(route, 'path', None) == '/api/v1/stream')

    def tearDown(self):
        self.temporary.cleanup()

    def expire(self):
        with self.store.connect() as db:
            db.execute('DELETE FROM sessions')

    async def test_stream_stays_open_across_old_lifetimes_and_disconnects_cleanly(self):
        elapsed = 0

        async def sleep(seconds):
            nonlocal elapsed
            elapsed += seconds

        clock = Mock(wraps=time)
        clock.monotonic.side_effect = lambda: elapsed
        with patch('aoc_spark.web.time', clock), patch('aoc_spark.web.asyncio.sleep', side_effect=sleep):
            iterator = (await self.endpoint(self.request)).body_iterator
            try:
                self.assertIn('retry:', await anext(iterator))
                self.assertIn('event: snapshot', await anext(iterator))
                for _ in range(25):
                    self.assertIn('heartbeat', await anext(iterator))
                self.assertGreaterEqual(elapsed, 50)
                self.request.is_disconnected.return_value = True
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
            finally:
                await iterator.aclose()

    async def test_logout_ends_stream(self):
        with patch('aoc_spark.web.asyncio.sleep', new=AsyncMock()):
            iterator = (await self.endpoint(self.request)).body_iterator
            try:
                await anext(iterator)
                self.assertIn('event: snapshot', await anext(iterator))
                self.expire()
                self.assertIn('event: auth_expired', await anext(iterator))
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
            finally:
                await iterator.aclose()

    async def test_expiry_during_snapshot_does_not_publish_data(self):
        annotate = self.store.annotate

        def slow_snapshot(value):
            self.expire()
            return annotate(value)

        iterator = (await self.endpoint(self.request)).body_iterator
        try:
            await anext(iterator)
            with patch.object(self.store, 'annotate', side_effect=slow_snapshot):
                self.assertIn('event: auth_expired', await anext(iterator))
            with self.assertRaises(StopAsyncIteration):
                await anext(iterator)
        finally:
            await iterator.aclose()

    async def test_shutdown_cancellation_ends_stream(self):
        iterator = (await self.endpoint(self.request)).body_iterator
        try:
            await anext(iterator)
            await anext(iterator)
            with patch('aoc_spark.web.asyncio.sleep', side_effect=asyncio.CancelledError):
                with self.assertRaises(StopAsyncIteration):
                    await anext(iterator)
        finally:
            await iterator.aclose()
