"""HTTP/SSE Responses interpretation; HTTP flow IDs directly correlate calls."""
from __future__ import annotations

from .codex_window import usage_window

import base64
from dataclasses import dataclass, field
import json

from src.proxy.live_capture import _body, codex_http_url
from .codex_context import Call, CodexContext
from .codex_responses import parse_codex_message
from .context import compare_snapshots, decode_response_bytes, parse_sse_data


@dataclass
class HttpCall:
    call: Call
    raw: bytearray = field(default_factory=bytearray)
    metadata: dict = field(default_factory=dict)
    blocks: int = 0
    gap: bool = False


class CodexHttpContext:
    def __init__(self, codex: CodexContext):
        self.codex = codex
        self.pending: dict[str, HttpCall] = {}

    def handles(self, event: dict) -> bool:
        request = event.get("payload", {}).get("request", {})
        return (event.get("flow_id") in self.pending or event["kind"] == "request.started"
                and request.get("method") == "POST" and codex_http_url(request.get("url", "")))

    def consume(self, event: dict) -> list[dict]:
        kind, flow_id, sequence = event["kind"], event.get("flow_id"), event["sequence"]
        if kind == "stream.gap":
            results = [self.finish(flow, state, sequence, "capture_gap") for flow, state in self.pending.items()]
            self.pending.clear()
            return results
        if kind == "request.started":
            request = event["payload"]["request"]
            decoded = request.get("body", {}).get("decoded", {})
            value = decoded.get("value") if isinstance(decoded, dict) and decoded.get("kind") == "json" else None
            if not isinstance(value, dict):
                return []
            snapshot = self.codex._snapshot(event, value, http_request=request)
            self.pending[flow_id] = HttpCall(Call(snapshot))
            reference = value.get("previous_response_id")
            predecessor = self.codex.completed.get(reference) if isinstance(reference, str) else None
            diff = compare_snapshots(predecessor, snapshot)
            if diff["relationship"] == "compaction_candidate":
                diff["relationship"] = "chronological"
            diff.update(provider="codex", comparison_lineage=f"codex:responses:{flow_id}",
                        predecessor_basis="previous_response_id" if predecessor else "no_observed_predecessor",
                        predecessor_confidence="medium" if predecessor else "none",
                        context_visibility={"scope": "wire_request_fields_only", "previous_response_id": reference,
                                            "predecessor_observed": predecessor is not None, "server_context": "not_reconstructed"})
            return [diff]
        state = self.pending.get(flow_id)
        if state is None:
            return []
        if kind == "response.started":
            state.metadata = dict(event["payload"])
        if kind == "response.block":
            payload = event["payload"]
            if payload["block_index"] != state.blocks or payload["offset"] != len(state.raw):
                state.gap = True
            state.blocks += 1
            try:
                state.raw.extend(base64.b64decode(payload["body"]["wire"]["data"], validate=True))
            except (ValueError, TypeError):
                state.gap = True
        if kind not in {"flow.completed", "flow.error"}:
            return []
        self.pending.pop(flow_id)
        if kind == "flow.error":
            return [self.finish(flow_id, state, sequence, "transport_error")]
        if event["payload"]["response_body_bytes"] != len(state.raw) or event["payload"]["response_blocks"] != state.blocks:
            state.gap = True
        return self.completed(flow_id, state, sequence)

    @staticmethod
    def headers(state: HttpCall) -> dict:
        return {str(k).lower(): str(v) for k, v in state.metadata.get("headers", {}).items()}

    def finish(self, flow_id: str, state: HttpCall, sequence: int, status: str, response: dict | None = None) -> dict:
        result = self.codex._response(state.call, sequence, response or {}, status)
        headers = self.headers(state)
        result["correlation"] = {"basis": "exact_http_flow_id", "confidence": "high"}
        result["exact_response"] = {"transport": "http", **state.metadata,
            "capture_completeness": "gap" if state.gap or status == "capture_gap" else "observed_blocks",
            "body": _body(bytes(state.raw), headers.get("content-type", ""), headers.get("content-encoding", ""))}
        return result

    def completed(self, flow_id: str, state: HttpCall, sequence: int) -> list[dict]:
        if state.gap:
            return [self.finish(flow_id, state, sequence, "capture_gap")]
        status_code = state.metadata.get("status_code")
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            return [self.finish(flow_id, state, sequence, "http_error_or_missing_headers")]
        headers = self.headers(state)
        text = decode_response_bytes(bytes(state.raw), headers.get("content-encoding", ""))
        if text is None:
            return [self.finish(flow_id, state, sequence, "undecodable_response")]
        terminal = None
        records = parse_sse_data(text) if "event-stream" in headers.get("content-type", "") else []
        for record in records:
            if record.get("type") == "response.output_item.done":
                index, item = record.get("output_index"), record.get("item")
                if type(index) is int and index >= 0 and isinstance(item, dict):
                    if index in state.call.output_items and state.call.output_items[index] != item:
                        state.call.conflicting_output_indices.add(index)
                    state.call.output_items[index] = item
            if record.get("type") in {"response.completed", "response.failed", "response.incomplete"}:
                if terminal is not None:
                    return [self.finish(flow_id, state, sequence, "ambiguous_terminal_events")]
                terminal = record
        if terminal is None:
            return [self.finish(flow_id, state, sequence, "missing_terminal_event")]
        response = terminal.get("response")
        if not isinstance(response, dict):
            return [self.finish(flow_id, state, sequence, "invalid_terminal_event")]
        response_id = response.get("id")
        state.call.response_id = response_id if isinstance(response_id, str) else None
        status = terminal["type"].split(".")[1]
        result = [self.finish(flow_id, state, sequence, status, response)]
        if status != "completed":
            return result
        if isinstance(response_id, str) and response_id:
            self.codex.completed[response_id] = None if response_id in self.codex.completed else state.call.snapshot
        parsed = parse_codex_message("server_to_client", json.dumps(terminal))
        usage = parsed["usage"] if parsed else {}
        used = usage.get("input_tokens")
        result.append({"kind": "context.usage", "provider": "codex", "flow_id": flow_id, "sequence": sequence,
            "stream_identity": state.call.snapshot.stream_identity, "used_input_tokens": used, "components": usage,
            **usage_window(state.call.snapshot.exact_request, used, self.codex.catalog, self.codex.window, self.codex.window_source),
            "usage_source": "wire_response_completed_usage" if used is not None else "usage_not_reported"})
        return result
