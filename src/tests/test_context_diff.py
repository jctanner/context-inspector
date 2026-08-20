from __future__ import annotations

import base64
import json
import unittest
import asyncio
import tempfile
import gzip
from pathlib import Path

from src.server.context import ContextEventStream, classify_request_purpose, classify_response_purpose, decode_response_bytes, derive_context_diffs, extract_sse_usage, normalize_request, reconstruct_sse_response


def request_event(sequence: int, payload: dict, flow_id: str | None = None) -> dict:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return {
        "kind": "request.started", "sequence": sequence, "flow_id": flow_id or f"flow-{sequence}",
        "payload": {"request": {"method": "POST", "url": "https://api.example/messages", "http_version": "HTTP/2",
            "headers": {"content-type": "application/json"},
            "body": {"wire": {"encoding": "base64", "data": base64.b64encode(raw).decode(), "byte_length": len(raw), "content_encoding": "identity"},
                     "decoded": {"kind": "json", "value": payload}, "decode_status": "decoded"}}},
    }


class ContextDiffTests(unittest.TestCase):
    def test_classifies_exact_internal_count_probe_conservatively(self) -> None:
        purpose = classify_request_purpose({
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "count"}],
        })
        self.assertEqual(purpose["classification"], "likely_internal_token_counting")
        self.assertEqual(purpose["confidence"], "medium")
        self.assertIn("max_tokens_equals_one", purpose["evidence"])

    def test_title_generation_is_classified_from_request_before_response(self) -> None:
        purpose = classify_request_purpose({
            "system": "Generate a concise conversation title as JSON.",
            "messages": [{"role": "user", "content": "Tell a funny story"}],
        })
        self.assertEqual(purpose["classification"], "likely_internal_title_generation")
        self.assertEqual(purpose["confidence"], "medium")

    def test_title_words_in_tool_descriptions_do_not_classify_main_request(self) -> None:
        purpose = classify_request_purpose({
            "system": "You are a coding agent.",
            "tools": [{"name": "shell", "description": 'Run gh pr create --title "the PR title"'}],
            "messages": [{"role": "user", "content": "Tell me a story"}],
        })
        self.assertEqual(purpose["classification"], "unclassified")

    def test_internal_count_probe_has_a_separate_comparison_lineage(self) -> None:
        count = request_event(1, {
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "count"}],
        })
        session = request_event(2, {
            "max_tokens": 32000,
            "messages": [{"role": "user", "content": [{
                "type": "text",
                "text": "<system-reminder>\nInjected memory index\n</system-reminder>",
            }]}],
        })
        diffs = derive_context_diffs([count, session])
        self.assertEqual(diffs[0]["relationship"], "initial")
        self.assertEqual(diffs[1]["relationship"], "initial")
        self.assertIsNone(diffs[1]["predecessor_flow_id"])
        self.assertNotEqual(diffs[0]["comparison_lineage"], diffs[1]["comparison_lineage"])
        self.assertFalse(any(change["change"] == "transformed" for change in diffs[1]["changes"]))

        repeated_count = request_event(3, {
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "count"}],
        })
        repeated = derive_context_diffs([count, session, repeated_count])[-1]
        self.assertEqual(repeated["predecessor_flow_id"], "flow-1")
        self.assertEqual(repeated["predecessor_confidence"], "medium")

    def test_wrapper_blocks_expose_inferred_harness_origin(self) -> None:
        event = request_event(1, {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "<system-reminder>memory</system-reminder>"},
            {"type": "text", "text": "<command-name>/context</command-name>"},
        ]}]})
        snapshot = normalize_request(event)
        assert snapshot is not None
        self.assertEqual(snapshot.blocks[0].origin, "harness_injected_system_reminder")
        self.assertEqual(snapshot.blocks[0].origin_confidence, "medium")
        self.assertIn("system_reminder_wrapper", snapshot.blocks[0].origin_evidence)
        self.assertEqual(snapshot.blocks[1].origin, "harness_injected_local_command")
        self.assertEqual(snapshot.blocks[1].origin_confidence, "medium")

    def test_title_generation_requires_request_and_response_evidence(self) -> None:
        event = request_event(1, {"system": "Generate a concise conversation title as JSON.", "messages": [{"role": "user", "content": "Tell a funny story"}]})
        snapshot = normalize_request(event)
        assert snapshot is not None
        title = {"content_blocks": [{"type": "text", "text": '```json\n{"title":"Funny story"}\n```'}]}
        purpose = classify_response_purpose(snapshot, title)
        self.assertEqual(purpose["classification"], "likely_internal_title_generation")
        self.assertEqual(purpose["confidence"], "medium")
        ordinary = classify_response_purpose(snapshot, {"content_blocks": [{"type": "text", "text": "A story"}]})
        self.assertEqual(ordinary["classification"], "unclassified")

    def test_reconstructs_semantic_response_blocks_from_sse_deltas(self) -> None:
        sse = "\n\n".join([
            'data: {"type":"message_start","message":{"id":"msg-1","model":"sonnet"}}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hello "}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"world"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":7}}',
        ]) + "\n\n"
        response = reconstruct_sse_response(sse)
        self.assertEqual(response["model"], "sonnet")
        self.assertEqual(response["stop_reason"], "end_turn")
        self.assertEqual(response["output_tokens"], 7)
        self.assertEqual(response["content_blocks"], [{"type": "text", "text": "hello world"}])

    def test_decodes_complete_gzip_response_not_individual_transport_chunks(self) -> None:
        text = 'event: message_start\ndata: {"usage":{"input_tokens":7}}\n\n'
        compressed = gzip.compress(text.encode())
        self.assertEqual(decode_response_bytes(compressed, "gzip"), text)
        self.assertIsNone(decode_response_bytes(compressed[:1], "gzip"))

    def test_extracts_usage_across_sse_chunk_boundary(self) -> None:
        first = 'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":12,'
        usages, remainder = extract_sse_usage(first)
        self.assertEqual(usages, [])
        second = '"cache_creation_input_tokens":3,"cache_read_input_tokens":40}}}\n\n'
        usages, remainder = extract_sse_usage(remainder + second)
        self.assertEqual(usages, [{"input_tokens": 12, "cache_creation_input_tokens": 3, "cache_read_input_tokens": 40}])
        self.assertEqual(remainder, "")
    def test_normalizes_system_tools_messages_and_preserves_metrics(self) -> None:
        event = request_event(1, {
            "system": [{"type": "text", "text": "rules"}],
            "tools": [{"name": "lookup", "input_schema": {"type": "object"}}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            "input_tokens": 123,
        })
        snapshot = normalize_request(event)
        assert snapshot is not None
        self.assertEqual([block.category for block in snapshot.blocks], ["system", "tools", "messages"])
        self.assertEqual(snapshot.token_count, 123)
        self.assertEqual(snapshot.token_count_source, "input_tokens")
        self.assertEqual(snapshot.body_byte_count, event["payload"]["request"]["body"]["wire"]["byte_length"])

    def test_reports_retained_added_removed_and_transformed_blocks(self) -> None:
        first = request_event(1, {"system": "rules", "messages": [
            {"role": "user", "content": "keep"}, {"role": "assistant", "content": "old"},
        ]})
        second = request_event(2, {"system": "rules", "messages": [
            {"role": "user", "content": "keep"}, {"role": "assistant", "content": "new"},
            {"role": "user", "content": "added"},
        ]})
        diff = derive_context_diffs([first, second])[-1]
        self.assertGreaterEqual(diff["counts"]["retained"], 2)
        self.assertEqual(diff["counts"]["transformed"], 1)
        self.assertEqual(diff["counts"]["added"], 1)

    def test_shifted_identical_block_is_retained_and_marked_moved(self) -> None:
        first = request_event(1, {"messages": [{"role": "user", "content": "remove"}, {"role": "assistant", "content": "keep"}]})
        second = request_event(2, {"messages": [{"role": "assistant", "content": "keep"}]})
        diff = derive_context_diffs([first, second])[-1]
        self.assertEqual(diff["relationship"], "compaction_candidate")
        self.assertTrue(any(change.get("moved") for change in diff["changes"] if change["change"] == "retained"))
        self.assertEqual(diff["counts"]["removed"], 1)

    def test_duplicate_does_not_advance_comparison_baseline(self) -> None:
        original = request_event(1, {"messages": [{"role": "user", "content": "one"}]})
        retry = request_event(2, {"messages": [{"role": "user", "content": "one"}]})
        next_turn = request_event(3, {"messages": [{"role": "user", "content": "two"}]})
        diffs = derive_context_diffs([original, retry, next_turn])
        self.assertEqual(diffs[1]["relationship"], "retry_or_duplicate")
        self.assertEqual(diffs[2]["predecessor_flow_id"], "flow-1")

    def test_non_model_json_is_ignored_and_missing_tokens_are_explicit(self) -> None:
        ignored = request_event(1, {"grant_type": "token"})
        model = request_event(2, {"messages": []})
        self.assertIsNone(normalize_request(ignored))
        diff = derive_context_diffs([ignored, model])[0]
        self.assertIsNone(diff["metrics"]["token_count"])
        self.assertIsNone(diff["metrics"]["token_count_source"])

    def test_stable_agent_header_maintains_independent_predecessor(self) -> None:
        parent_one = request_event(1, {"messages": [{"role": "user", "content": "parent one"}]})
        worker_one = request_event(2, {"messages": [{"role": "user", "content": "worker one"}]})
        worker_one["payload"]["request"]["headers"]["x-claude-code-agent-id"] = "worker-7"
        worker_two = request_event(3, {"messages": [{"role": "user", "content": "worker two"}]})
        worker_two["payload"]["request"]["headers"]["x-claude-code-agent-id"] = "worker-7"
        parent_two = request_event(4, {"messages": [{"role": "user", "content": "parent two"}]})
        diffs = derive_context_diffs([parent_one, worker_one, worker_two, parent_two])
        self.assertIsNone(diffs[1]["predecessor_flow_id"])
        self.assertEqual(diffs[2]["predecessor_flow_id"], "flow-2")
        self.assertEqual(diffs[2]["predecessor_confidence"], "high")
        self.assertEqual(diffs[3]["predecessor_flow_id"], "flow-1")


class ContextEventStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_reassembles_gzip_sse_before_emitting_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            request = request_event(1, {"messages": [{"role": "user", "content": "one"}]})
            common = {"protocol_version": "1.0", "session_id": "session-test",
                      "occurred_at": "2026-08-19T12:00:00Z",
                      "sanitization": {"applied": True, "policy": "test", "redacted_fields": []}}
            request.update(common | {"event_id": "request"})
            sse = 'data: {"type":"message_start","message":{"usage":{"input_tokens":10,"cache_creation_input_tokens":20,"cache_read_input_tokens":30}}}\n\n'
            compressed = gzip.compress(sse.encode())
            events = [request, {
                **common, "event_id": "headers", "sequence": 2, "kind": "response.started", "flow_id": "flow-1",
                "payload": {"status_code": 200, "reason": "OK", "http_version": "HTTP/2",
                            "headers": {"Content-Type": "text/event-stream", "Content-Encoding": "gzip"}},
            }]
            for index, chunk in enumerate(compressed, start=3):
                events.append({**common, "event_id": f"block-{index}", "sequence": index,
                    "kind": "response.block", "flow_id": "flow-1", "payload": {
                        "block_index": index - 3, "offset": index - 3, "final": False,
                        "body": {"wire": {"encoding": "base64", "data": base64.b64encode(bytes([chunk])).decode(),
                                          "byte_length": 1, "content_encoding": "gzip"},
                                 "decoded": None, "decode_status": "failed"}}})
            events.append({**common, "event_id": "complete", "sequence": len(events) + 1,
                           "kind": "flow.completed", "flow_id": "flow-1", "payload": {
                               "request_body_bytes": 1, "response_body_bytes": len(compressed),
                               "response_blocks": len(compressed), "archive": {"status": "written", "record_id": "fixture"}}})
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            stream = ContextEventStream(path, "session-test", 200, "test limit").events()
            await asyncio.wait_for(anext(stream), 1)
            usage = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(usage["used_input_tokens"], 60)
            self.assertEqual(usage["usage_source"], "wire_response_sse_usage_reassembled")
            response = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(response["kind"], "context.response")
            self.assertEqual(response["flow_id"], "flow-1")
            self.assertEqual(response["purpose"]["classification"], "unclassified")
            self.assertEqual(response["exact_response"]["body"]["wire"]["byte_length"], len(compressed))
            await stream.aclose()

    async def test_replay_builds_baseline_before_after_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            events = [
                request_event(1, {"messages": [{"role": "user", "content": "one"}]}),
                request_event(2, {"messages": [{"role": "user", "content": "two"}]}),
            ]
            for event in events:
                event.update({
                    "protocol_version": "1.0", "event_id": f"event-{event['sequence']}",
                    "session_id": "session-test", "occurred_at": "2026-08-19T12:00:00Z",
                    "sanitization": {"applied": True, "policy": "test", "redacted_fields": []},
                })
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            stream = ContextEventStream(path, "session-test").events(after=1)
            diff = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(diff["sequence"], 2)
            self.assertEqual(diff["predecessor_flow_id"], "flow-1")
            await stream.aclose()

    async def test_emits_usage_correlated_to_request_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            request = request_event(1, {"messages": [{"role": "user", "content": "one"}]})
            request.update({"protocol_version": "1.0", "event_id": "request", "session_id": "session-test",
                            "occurred_at": "2026-08-19T12:00:00Z", "sanitization": {"applied": True, "policy": "test", "redacted_fields": []}})
            sse = 'data: {"type":"message_start","message":{"usage":{"input_tokens":10,"cache_creation_input_tokens":20,"cache_read_input_tokens":30}}}\n\n'
            raw = sse.encode()
            response = {"protocol_version": "1.0", "event_id": "response", "session_id": "session-test", "sequence": 2,
                "occurred_at": "2026-08-19T12:00:01Z", "kind": "response.block", "flow_id": "flow-1",
                "sanitization": {"applied": True, "policy": "test", "redacted_fields": []},
                "payload": {"block_index": 0, "offset": 0, "final": False, "body": {
                    "wire": {"encoding": "base64", "data": base64.b64encode(raw).decode(), "byte_length": len(raw), "content_encoding": "identity"},
                    "decoded": {"kind": "sse", "value": sse}, "decode_status": "decoded"}}}
            path.write_text(json.dumps(request) + "\n" + json.dumps(response) + "\n")
            stream = ContextEventStream(path, "session-test", 200, "test limit").events()
            await asyncio.wait_for(anext(stream), 1)
            usage = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(usage["kind"], "context.usage")
            self.assertEqual(usage["used_input_tokens"], 60)
            self.assertEqual(usage["percent"], 30.0)
            self.assertEqual(usage["context_window_source"], "test limit")
            await stream.aclose()


if __name__ == "__main__":
    unittest.main()
