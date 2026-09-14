import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from src.server.context import ContextEventStream
from src.server.flows import FlowEventStream
from src.tests.test_context_diff import request_event


class PartialCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_record_is_retried_by_both_readers(self):
        for reader in (FlowEventStream, ContextEventStream):
            with self.subTest(reader=reader.__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "events.jsonl"
                event = request_event(1, {"messages": [{"role": "user", "content": "fixture"}]})
                event.update(protocol_version="1.0", event_id="fixture", session_id="session-test",
                             occurred_at="2026-09-13T12:00:00Z",
                             sanitization={"applied": True, "policy": "test", "redacted_fields": []})
                line = json.dumps(event) + "\n"
                split = len(line) // 2
                path.write_text(line[:split])
                stream = reader(path, "session-test").events()
                pending = asyncio.create_task(anext(stream))
                try:
                    await asyncio.sleep(0.12)
                    self.assertFalse(pending.done(), "partial JSON must not be emitted as a permanent error")
                    with path.open("a") as writer:
                        writer.write(line[split:])
                    observed = await asyncio.wait_for(pending, 1)
                    self.assertEqual(observed["sequence"], 1)
                    self.assertNotIn("type", observed)
                finally:
                    if not pending.done():
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
                    await stream.aclose()
