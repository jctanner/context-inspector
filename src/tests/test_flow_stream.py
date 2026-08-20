from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from src.proxy.live_capture import JsonlEmitter
from src.server.flows import FlowEventStream


class FlowEventStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_replays_after_sequence_and_reports_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            emitter = JsonlEmitter(path, "session-test")
            emitter.emit("flow.error", "flow-1", {"stage": "connect", "code": "failed", "message": "safe", "retryable": True, "request_observed": False, "response_observed": False})
            emitter.emit("flow.error", "flow-2", {"stage": "connect", "code": "failed", "message": "safe", "retryable": True, "request_observed": False, "response_observed": False})
            stream = FlowEventStream(path, "session-test").events(after=1)
            event = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(event["sequence"], 2)
            await stream.aclose()


if __name__ == "__main__":
    unittest.main()
