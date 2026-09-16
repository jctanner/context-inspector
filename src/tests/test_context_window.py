"""Synthetic fixtures only: never read or mutate a live Claude session."""

import asyncio
import base64
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.server.config import Settings
from src.server.context import ContextEventStream
from src.server.context_window import resolve_window
from src.tests.test_context_diff import request_event


class WindowTests(unittest.TestCase):
    def test_model_ids_and_provenance(self):
        for model, expected in [
            ("claude-sonnet-5", 1_000_000),
            ("claude-sonnet-4-6", 200_000),
            ("us.anthropic.claude-sonnet-4-6-v1:0", 200_000),
            ("claude-opus-4-6", 200_000),
            ("claude-haiku-4-5-20251001", 200_000),
            ("claude-haiku-4-5@20251001", 200_000),
            ("us.anthropic.claude-opus-4-6-v1:0", 200_000),
        ]:
            with self.subTest(model=model):
                request = request_event(1, {"model": model})["payload"]["request"]
                window, source = resolve_window(request)
                self.assertEqual(window, expected)
                self.assertIn("request body model", source)
                self.assertIn("not a wire-observed limit", source)
        for url, expected in [
            ("https://example/publishers/anthropic/models/claude-sonnet-5:streamRawPredict", 1_000_000),
            ("https://example/publishers/anthropic/models/claude-sonnet-4-6:streamRawPredict", 200_000),
            ("https://example/model/us.anthropic.claude-opus-4-6-v1%3A0/invoke-with-response-stream", 200_000),
        ]:
            window, source = resolve_window({"url": url})
            self.assertEqual(window, expected)
            self.assertIn("request URL model", source)

    def test_unknown_missing_and_launch_fallback(self):
        self.assertEqual(resolve_window({}, fallback_model="claude-sonnet-5")[0], 1_000_000)
        self.assertIn("launch model fallback", resolve_window({}, fallback_model="claude-sonnet-5")[1])
        for model in ["claude-sonnet-50", "claude-sonnet-5-unknown", "unknown"]:
            request = request_event(1, {"model": model})["payload"]["request"]
            # Unknown wire model must not silently inherit the launch model.
            window, source = resolve_window(request, fallback_model="claude-sonnet-5")
            self.assertEqual(window, 200_000)
            self.assertIn("unverified", source)
        self.assertIn("unverified", resolve_window({})[1])

    def test_explicit_override_including_200k_wins(self):
        request = request_event(1, {"model": "claude-sonnet-5"})["payload"]["request"]
        for limit in [200_000, 500_000, 1_000_000]:
            with patch.dict(os.environ, {"CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS": str(limit)}):
                settings = Settings.from_environment()
            self.assertEqual(resolve_window(request, override=settings.context_window_tokens,
                                           override_source=settings.context_window_source),
                             (limit, "environment override"))
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(Settings.from_environment().context_window_tokens)


class WindowStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_sonnet_46_percentage_and_launch_fallback(self):
        from src.server.context import normalize_request

        snapshot = normalize_request(request_event(1, {"model": "claude-sonnet-4-6", "messages": []}))
        usage = ContextEventStream(Path("unused"), "session-test").usage_window(snapshot, 60_000)
        self.assertEqual(usage["context_window_tokens"], 200_000)
        self.assertEqual(usage["percent"], 30)
        self.assertEqual(resolve_window({}, fallback_model="claude-sonnet-4-6")[0], 200_000)

    async def test_opus_percentage_and_override(self):
        from src.server.context import normalize_request

        snapshot = normalize_request(request_event(1, {"model": "claude-opus-4-6", "messages": []}))
        usage = ContextEventStream(Path("unused"), "session-test").usage_window(snapshot, 60_000)
        self.assertEqual(usage["percent"], 30)
        self.assertIn("deployment model default", usage["context_window_source"])
        override = ContextEventStream(Path("unused"), "session-test", 1_000_000).usage_window(snapshot, 60_000)
        self.assertEqual(override["percent"], 6)

    async def test_live_and_reassembled_replay_use_each_requests_model(self):
        for compressed in [False, True]:
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as directory:
                common = {"protocol_version": "1.0", "session_id": "session-test",
                          "occurred_at": "2026-09-15T12:00:00Z",
                          "sanitization": {"applied": True, "policy": "test", "redacted_fields": []}}
                events = []

                def append(kind, flow, payload):
                    seq = len(events) + 1
                    events.append({**common, "event_id": str(seq), "sequence": seq,
                                   "kind": kind, "flow_id": flow, "payload": payload})

                for flow, model in [("sonnet", "claude-sonnet-5"), ("haiku", "claude-haiku-4-5")]:
                    request = request_event(1, {"model": model, "messages": []})
                    append("request.started", flow, request["payload"])
                # Responses arrive in reverse order; resolve by exact flow, not latest model.
                for flow in ["haiku", "sonnet"]:
                    sse = 'data: {"type":"message_start","message":{"usage":{"input_tokens":2,"cache_creation_input_tokens":289586,"cache_read_input_tokens":0}}}\n\n'
                    raw = gzip.compress(sse.encode()) if compressed else sse.encode()
                    append("response.started", flow, {"status_code": 200, "reason": "OK", "http_version": "HTTP/2",
                           "headers": {"content-type": "text/event-stream", "content-encoding": "gzip" if compressed else "identity"}})
                    append("response.block", flow, {"block_index": 0, "offset": 0, "final": False, "body": {
                        "wire": {"encoding": "base64", "data": base64.b64encode(raw).decode(), "byte_length": len(raw),
                                 "content_encoding": "gzip" if compressed else "identity"},
                        "decoded": None if compressed else {"kind": "sse", "value": sse},
                        "decode_status": "failed" if compressed else "decoded"}})
                    append("flow.completed", flow, {"request_body_bytes": 1, "response_body_bytes": len(raw),
                           "response_blocks": 1, "archive": {"status": "written", "record_id": "fixture"}})
                path = Path(directory) / "events.jsonl"
                path.write_text("".join(json.dumps(event) + "\n" for event in events))
                # Cursor omits request cards, but their model evidence must survive replay.
                stream = ContextEventStream(path, "session-test").events(after=2, mark_ready=True)
                usages = {}
                try:
                    while True:
                        event = await asyncio.wait_for(anext(stream), 1)
                        self.assertNotEqual(event.get("type"), "stream-error", event)
                        if event.get("type") == "replay-ready":
                            break
                        if event.get("kind") == "context.usage":
                            usages[event["flow_id"]] = event
                finally:
                    await stream.aclose()
                self.assertEqual(usages["sonnet"]["used_input_tokens"], 289588)
                self.assertEqual(usages["sonnet"]["context_window_tokens"], 1_000_000)
                self.assertAlmostEqual(usages["sonnet"]["percent"], 28.9588)
                self.assertEqual(usages["haiku"]["context_window_tokens"], 200_000)
                self.assertEqual(usages["haiku"]["percent"], 100)
