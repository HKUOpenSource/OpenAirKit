"""Exercise API task persistence across executor EOF without operating a stack."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

import httpx

from aoc_spark.web import create_app, password_hash


class ControlStreamTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, messages, query_result, expected, expected_error=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            salt = '12' * 16
            (root / 'auth.json').write_text(json.dumps({
                'salt': salt, 'password_hash': password_hash('test-password', salt)}))
            app = create_app(dict(auth_file=str(root / 'auth.json'), database=str(root / 'history.db'),
                                  snapshot=str(root / 'snapshot.json'), frontend=str(root)))
            store = app.state.store
            completed = asyncio.Event()
            update = store.update_control
            requests = []

            def persist(identifier, message):
                result = update(identifier, message)
                if result['state'] in {'succeeded', 'failed', 'cancelled', 'interrupted'}:
                    completed.set()
                return result

            async def connection(_path):
                reader = asyncio.StreamReader()
                writer = Mock()
                writer.drain = AsyncMock()
                writer.wait_closed = AsyncMock()

                def write(data):
                    request = json.loads(data)
                    requests.append(request)
                    if request['command'] == 'run':
                        replies = messages
                    else:
                        self.assertEqual(request['command'], 'query')
                        if query_result is None:
                            reader.set_exception(ConnectionResetError('Executor unavailable'))
                            return
                        replies = [query_result]
                    for message in replies:
                        reader.feed_data(json.dumps(message).encode() + b'\n')
                    reader.feed_eof()

                writer.write.side_effect = write
                return reader, writer

            with patch('aoc_spark.web.asyncio.open_unix_connection', side_effect=connection), \
                    patch.object(store, 'update_control', side_effect=persist):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                             base_url='http://testserver') as client:
                    csrf = (await client.post('/api/v1/login', json={'password': 'test-password'})).json()['csrf']
                    response = await client.post('/api/v1/control', headers={'X-CSRF-Token': csrf},
                                                 json={'action': 'start', 'confirmation': True})
                    self.assertEqual(response.status_code, 200)
                    identifier = response.json()['id']
                    await asyncio.wait_for(completed.wait(), 1)
                    # Allow terminal audit/transport cleanup to finish before closing the database.
                    await asyncio.sleep(0)
                    result = store.control(identifier)
                    self.assertEqual(result['state'], expected)
                    self.assertEqual(result['error'], expected_error)
                    self.assertEqual(store.create_control(str(uuid.uuid4()), 'stop')['state'], 'queued')
                    self.assertTrue(all(r['task_id'] == identifier for r in requests))
                    self.assertEqual(sum(r['command'] == 'run' for r in requests), 1)
                    return requests

    async def test_running_eof_queries_original_task_and_releases_operation_lock(self):
        requests = await self.exercise([{'state': 'running'}], {'state': 'succeeded'}, 'succeeded')
        self.assertEqual([r['command'] for r in requests], ['run', 'query'])

    async def test_eof_before_first_message_marks_unknown_task_interrupted(self):
        await self.exercise([], {'state': 'unknown'}, 'interrupted', 'executor_task_unknown')

    async def test_eof_with_unavailable_executor_marks_task_interrupted(self):
        await self.exercise([{'state': 'running'}], None, 'interrupted', 'executor_unavailable')

    async def test_terminal_result_does_not_query_or_repeat_operation(self):
        requests = await self.exercise([{'state': 'running'}, {'state': 'succeeded'}], None, 'succeeded')
        self.assertEqual([r['command'] for r in requests], ['run'])
