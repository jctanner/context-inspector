"""Synthetic wire fixtures; no account credentials or model service calls."""
import asyncio
import base64
import json
from pathlib import Path
import tempfile
import unittest

from src.server.codex_context import CodexContext
from src.server.context import ContextEventStream
from src.server.context_index import ContextIndex
from src.protocol.events import validate_event


class Wire:
    def __init__(self):
        self.sequence = 0
        self.indices = {}
        self.events = []

    def message(self, direction, value, connection="socket", **overrides):
        self.sequence += 1
        raw = json.dumps(value, separators=(",", ":")).encode()
        index = self.indices.get(connection, 0)
        self.indices[connection] = index + 1
        event = {
            "protocol_version": "1.1", "event_id": f"event-{self.sequence}",
            "session_id": "session-test", "sequence": self.sequence,
            "occurred_at": "2026-09-23T12:00:00Z", "kind": "websocket.message", "flow_id": connection,
            "sanitization": {"applied": True, "policy": "synthetic", "redacted_fields": []},
            "payload": {"message_index": index, "direction": direction, "message_type": "text", "timestamp": 1.0,
                        "body": {"wire": {"encoding": "base64", "data": base64.b64encode(raw).decode(), "byte_length": len(raw), "content_encoding": "identity"},
                                 "decoded": {"kind": "json", "value": value}, "decode_status": "decoded"}},
        }
        event["payload"].update(overrides)
        validate_event(event)
        self.events.append(event)
        return event

    def create(self, **fields):
        return self.message("client_to_server", {"type": "response.create", "input": [{"role": "user", "content": "hello"}], **fields})

    def server(self, kind="created", rid="resp-1", lane=None, **fields):
        return self.message("server_to_client", {"type": f"response.{kind}", "response": {"id": rid, **fields}, **({"stream_id": lane} if lane else {})})


class CodexContextTests(unittest.TestCase):
    def setUp(self):
        self.wire = Wire()
        self.adapter = CodexContext()

    def consume(self, event):
        return self.adapter.consume(event)

    def test_tool_round_trip_links_only_observed_previous_response_and_retains_evidence(self):
        first = self.consume(self.wire.create(instructions="rules", tools=[{"type": "function", "name": "lookup"}]))[0]
        self.consume(self.wire.server())
        terminal = self.wire.server("completed", output=[{"type": "function_call", "call_id": "call-1", "name": "lookup", "arguments": "{}"}], usage={"input_tokens": 100, "input_tokens_details": {"cached_tokens": 60}, "output_tokens": 9})
        reply, usage = self.consume(terminal)
        self.assertEqual(reply["flow_id"], first["flow_id"])
        self.assertEqual(reply["exact_response"]["messages"][-1]["body"], terminal["payload"]["body"])
        self.assertEqual(reply["response"]["content_blocks"][0]["value"]["call_id"], "call-1")
        self.assertEqual(usage["occurred_at"], "2026-09-23T12:00:00Z")
        self.assertEqual(usage["used_input_tokens"], 100)
        self.assertEqual(usage["components"]["uncached_input_tokens"], 40)
        self.assertIsNone(usage["percent"])
        second = self.consume(self.wire.create(previous_response_id="resp-1", input=[{"type": "function_call_output", "call_id": "call-1", "output": "found"}]))[0]
        self.assertEqual(second["predecessor_flow_id"], first["flow_id"])
        self.assertEqual(second["predecessor_basis"], "previous_response_id_with_lane_order_pairing")
        self.assertEqual(second["context_visibility"]["scope"], "wire_request_fields_only")
        self.assertEqual(second["stream_identity"]["classification"], "unclassified")
        self.assertNotEqual(second["relationship"], "compaction_candidate")

    def test_interleaved_named_lanes_and_reordered_completions(self):
        a = self.consume(self.wire.create(stream_id="a"))[0]
        b = self.consume(self.wire.create(stream_id="b"))[0]
        self.consume(self.wire.server(rid="r-a", lane="a"))
        self.consume(self.wire.server(rid="r-b", lane="b"))
        rb = self.consume(self.wire.server("completed", "r-b", "b", usage={"input_tokens": 7}))[0]
        ra = self.consume(self.wire.server("completed", "r-a", "a", usage={"input_tokens": 5}))[0]
        self.assertEqual(rb["flow_id"], b["flow_id"])
        self.assertEqual(ra["flow_id"], a["flow_id"])
        self.assertNotEqual(a["flow_id"], b["flow_id"])

    def test_completed_items_survive_omitted_terminal_output(self):
        self.consume(self.wire.create())
        self.consume(self.wire.server())
        item = {"type": "message", "content": [{"type": "output_text", "text": "observed reply"}]}
        observed = self.wire.message("server_to_client", {
            "type": "response.output_item.done", "response_id": "resp-1", "output_index": 0, "item": item})
        self.consume(observed)
        result = self.consume(self.wire.server("completed"))[0]
        self.assertEqual(result["response"]["content_blocks"], [{"type": "text", "text": "observed reply"}])
        self.assertEqual(result["response"]["output_source"], "observed_completed_output_items")
        self.assertEqual(result["exact_response"]["messages"][1]["body"], observed["payload"]["body"])

    def test_native_connection_controls_do_not_interrupt_pending_call(self):
        self.consume(self.wire.create())
        for kind in ("codex.rate_limits", "codex.response.metadata"):
            self.assertEqual(self.consume(self.wire.message("server_to_client", {"type": kind})), [])
        self.consume(self.wire.server())
        self.assertEqual(self.consume(self.wire.message("server_to_client", {"type": "responsesapi.websocket_timing"})), [])
        response, usage = self.consume(self.wire.server("completed", usage={"input_tokens": 12}))
        self.assertEqual(response["response"]["stop_reason"], "completed")
        self.assertEqual(usage["used_input_tokens"], 12)

    def test_conflicting_items_abstain_and_explicit_terminal_output_wins(self):
        for terminal_output in (None, []):
            with self.subTest(terminal_output=terminal_output):
                wire, adapter = Wire(), CodexContext()
                adapter.consume(wire.create())
                adapter.consume(wire.server())
                for text in ("first", "second"):
                    adapter.consume(wire.message("server_to_client", {
                        "type": "response.output_item.done", "response_id": "resp-1", "output_index": 0,
                        "item": {"type": "message", "content": [{"type": "output_text", "text": text}]}}))
                result = adapter.consume(wire.server("completed", **({} if terminal_output is None else {"output": terminal_output})))[0]
                self.assertEqual(result["response"]["content_blocks"], [])
                self.assertEqual(result["response"]["conflicting_output_indices"], [0])
                if terminal_output == []:
                    self.assertEqual(result["response"]["output_source"], "terminal_response_output")

    def test_same_lane_queue_uses_created_then_id_not_socket_as_call_id(self):
        a = self.consume(self.wire.create())[0]
        b = self.consume(self.wire.create())[0]
        self.consume(self.wire.server(rid="a"))
        ra = self.consume(self.wire.server("completed", "a"))[0]
        self.consume(self.wire.server(rid="b"))
        rb = self.consume(self.wire.server("completed", "b"))[0]
        self.assertEqual(ra["flow_id"], a["flow_id"])
        self.assertEqual(rb["flow_id"], b["flow_id"])
        self.assertIsNone(b["predecessor_flow_id"])

    def test_missing_predecessor_does_not_imply_empty_context(self):
        diff = self.consume(self.wire.create(previous_response_id="unseen"))[0]
        self.assertIsNone(diff["predecessor_flow_id"])
        self.assertFalse(diff["context_visibility"]["predecessor_observed"])
        self.assertEqual(diff["context_visibility"]["server_context"], "not_reconstructed")

    def test_gap_mismatched_id_and_missing_created_abstain_from_usage(self):
        for scenario in ("gap", "mismatch", "missing_created"):
            with self.subTest(scenario=scenario):
                self.setUp()
                self.consume(self.wire.create())
                if scenario != "missing_created":
                    self.consume(self.wire.server())
                final = self.wire.server("completed", "wrong" if scenario == "mismatch" else "resp-1", usage={"input_tokens": 4})
                if scenario == "gap":
                    final["payload"]["message_index"] += 1
                observed = self.consume(final)
                self.assertFalse(any(item["kind"] == "context.usage" for item in observed))
                self.assertNotEqual(observed[0]["response"]["stop_reason"], "completed")

    def test_duplicate_final_does_not_double_count(self):
        self.consume(self.wire.create())
        self.consume(self.wire.server())
        self.consume(self.wire.server("completed", usage={"input_tokens": 4}))
        self.assertEqual(self.consume(self.wire.server("completed", usage={"input_tokens": 4})), [])

    def test_missing_usage_is_unknown_and_explicit_window_is_labeled(self):
        self.adapter = CodexContext(1000, "test override")
        self.consume(self.wire.create())
        self.consume(self.wire.server())
        result = self.consume(self.wire.server("completed"))[-1]
        self.assertIsNone(result["used_input_tokens"])
        self.assertIsNone(result["percent"])
        self.assertEqual(result["context_window_source"], "test override")

    def test_socket_close_and_unscoped_error_mark_unfinished_calls(self):
        self.consume(self.wire.create())
        self.consume(self.wire.server())
        close = {"kind": "websocket.closed", "flow_id": "socket", "sequence": 3}
        self.assertEqual(self.consume(close)[0]["response"]["stop_reason"], "connection_closed_before_completion")
        self.assertEqual(self.consume(close), [])
        self.consume(self.wire.create())
        error = self.wire.message("server_to_client", {"type": "error", "error": {"code": "invalid_request"}})
        self.assertEqual(self.consume(error)[0]["response"]["stop_reason"], "unscoped_server_error")

    def test_unknown_items_and_instructions_keep_original_paths(self):
        event = self.wire.create(instructions="rules", input=[{"type": "future_item", "encrypted_content": "opaque"}])
        diff = self.consume(event)[0]
        self.assertEqual([change["after"]["path"] for change in diff["changes"]], ["instructions", "input/0"])
        self.assertEqual(diff["exact_request"]["body"], event["payload"]["body"])


class CodexReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_index_replay_cursor_lazy_details_and_usage(self):
        wire = Wire()
        wire.create()
        wire.server()
        wire.server("completed", output=[{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}], usage={"input_tokens": 10})
        wire.create(previous_response_id="resp-1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("".join(json.dumps(event) + "\n" for event in wire.events))
            index = ContextIndex(ContextEventStream(path, "session-test"))
            try:
                await asyncio.wait_for(index.ready.wait(), 2)
                self.assertIsNone(index.error)
                snapshot = index.snapshot()
                self.assertEqual(snapshot["total"], 2)
                self.assertEqual(snapshot["latest_usage"]["used_input_tokens"], 10)
                self.assertEqual(index.full[("socket~0", "context.response")]["response"]["content_blocks"], [{"type": "text", "text": "hello"}])
                stream = ContextEventStream(path, "session-test").events(after=3, mark_ready=True)
                replay = await anext(stream)
                self.assertEqual(replay["predecessor_flow_id"], "socket~0")
                self.assertEqual((await anext(stream))["type"], "replay-ready")
                await stream.aclose()
            finally:
                await index.close()
