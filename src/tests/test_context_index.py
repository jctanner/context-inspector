import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from src.server.context import ContextEventStream
from src.server.context_index import ContextIndex
from src.tests.test_context_diff import request_event


class ContextIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_summaries_pagination_lazy_evidence_and_live_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            records = []
            for n in range(1, 45):
                event = request_event(n, {"messages": [{"role": "user", "content": "sensitive fixture " * 1000 + str(n)}]})
                event.update(protocol_version="1.0", event_id=f"event-{n}", session_id="session-test",
                             occurred_at="2026-09-13T12:00:00Z", sanitization={"applied": True, "policy": "fixture", "redacted_fields": []})
                records.append(event)
            path.write_text("".join(json.dumps(event) + "\n" for event in records))
            index = ContextIndex(ContextEventStream(path, "session-test"))
            try:
                await asyncio.wait_for(index.ready.wait(), 3)
                first = index.snapshot()
                self.assertEqual(first["total"], 44)
                self.assertEqual(len(first["events"]), 25)
                self.assertEqual(first["events"][-1]["request_number"], 44)
                self.assertEqual(first["next_before"], 20)
                self.assertNotIn("sensitive fixture", json.dumps(first))
                second = index.snapshot(before=first["next_before"])
                self.assertEqual(len(second["events"]), 19)
                self.assertIsNone(second["next_before"])
                self.assertEqual(index.snapshot(after_sequence=42)["total"], 2)
                full = index.full[("flow-44", "context.diff")]
                self.assertTrue(full["changes"])
                self.assertIn("sensitive fixture", json.dumps(full["exact_request"]))
                self.assertLess(len(json.dumps(first)), len(json.dumps(list(index.full.values()))) / 10)
                # Snapshot cursor must include both derived updates at one sequence.
                event = {"kind": "context.usage", "flow_id": "flow-44", "sequence": 50}
                index.add(event)
                index.add({**event, "sequence": 51})
                self.assertEqual([event["cursor"] for event in index.journal[first["cursor"]:]], [45, 46])
                self.assertEqual(index.snapshot()["cursor"], 46)
            finally:
                await index.close()
