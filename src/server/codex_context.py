"""Responses WebSocket calls derived from preserved logical-message evidence.

Lane order pairs response.created with a pending create; captured response IDs
then pair terminal events. Only previous_response_id establishes a diff link.
Neither a lane nor a response ID establishes primary/subagent identity.
"""
from __future__ import annotations

import base64
import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .codex_responses import parse_codex_message
from .codex_window import usage_window
from .context import ContextBlock, ContextSnapshot, compare_snapshots


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass
class Call:
    snapshot: ContextSnapshot
    response_id: str | None = None
    messages: list[dict] = field(default_factory=list)
    output_items: dict[int, Any] = field(default_factory=dict)
    conflicting_output_indices: set[int] = field(default_factory=set)


class CodexContext:
    def __init__(self, window: int | None = None, window_source: str = "configured override", *, catalog: dict | None = None):
        self.catalog = catalog or {}
        self.window = window
        self.window_source = window_source
        self.pending: dict[tuple[str, str | None], deque[Call]] = defaultdict(deque)
        self.completed: dict[str, ContextSnapshot | None] = {}
        self.last_index: dict[str, int] = {}

    def consume(self, event: dict) -> list[dict]:
        kind = event["kind"]
        if kind == "stream.gap":
            results = self._interrupt(None, event["sequence"], "capture_gap")
            self.completed.clear()
            self.last_index.clear()
            return results
        if kind == "websocket.closed":
            return self._interrupt(event["flow_id"], event["sequence"], "connection_closed_before_completion")
        if kind != "websocket.message":
            return []
        connection = event["flow_id"]
        payload = event["payload"]
        index = payload["message_index"]
        results = []
        previous_index = self.last_index.get(connection, -1)
        if index != previous_index + 1:
            results += self._interrupt(connection, event["sequence"], "capture_gap")
            self.completed.clear()
            if index <= previous_index:
                return results
        self.last_index[connection] = index
        if payload["message_type"] != "text":
            return results + self._interrupt(connection, event["sequence"], "unsupported_message")
        try:
            raw = base64.b64decode(payload["body"]["wire"]["data"], validate=True)
            value = json.loads(raw)
        except (ValueError, UnicodeError, TypeError):
            return results + self._interrupt(connection, event["sequence"], "uninterpretable_message")
        if not isinstance(value, dict):
            return results + self._interrupt(connection, event["sequence"], "uninterpretable_message")
        lane = value.get("stream_id")
        if lane is not None and (not isinstance(lane, str) or not lane):
            return results + self._interrupt(connection, event["sequence"], "invalid_stream_id")
        key = (connection, lane)
        event_type = value.get("type")
        if payload["direction"] == "client_to_server":
            if event_type != "response.create":
                # Unknown client operations may cancel/reorder requests.
                return results + self._interrupt(connection, event["sequence"], "unsupported_client_operation")
            snapshot = self._snapshot(event, value)
            self.pending[key].append(Call(snapshot))
            reference = value.get("previous_response_id")
            predecessor = self.completed.get(reference) if isinstance(reference, str) else None
            diff = compare_snapshots(predecessor, snapshot)
            # These are message-local fields, never the reconstructed total context.
            if diff["relationship"] == "compaction_candidate":
                diff["relationship"] = "chronological"
            diff.update(
                provider="codex", comparison_lineage=f"codex:responses:{snapshot.flow_id}",
                predecessor_basis="previous_response_id_with_lane_order_pairing" if predecessor else "no_observed_predecessor",
                predecessor_confidence="medium" if predecessor else "none",
                context_visibility={"scope": "wire_request_fields_only", "previous_response_id": reference,
                                    "predecessor_observed": predecessor is not None,
                                    "server_context": "not_reconstructed"},
            )
            results.append(diff)
            return results
        queue = self.pending.get(key)
        if event_type in {"codex.rate_limits", "codex.response.metadata", "responsesapi.websocket_timing"}:
            # Observed native connection controls are not response lifecycle
            # events. Preserve them in the raw stream without call attribution.
            return results
        if event_type == "error":
            # A connection error (no named lane) cannot be assigned to one call.
            if lane is None:
                return results + self._interrupt(connection, event["sequence"], "unscoped_server_error")
            if queue:
                call = queue.popleft()
                call.messages.append(self._evidence(event))
                results.append(self._response(call, event["sequence"], {}, "error"))
            return results
        if not queue:
            return results  # Unmatched events remain available as raw messages.
        call = queue[0]
        response = value.get("response")
        response = response if isinstance(response, dict) else {}
        response_id = response.get("id") or value.get("response_id")
        if event_type == "response.created":
            if not isinstance(response_id, str) or not response_id:
                return results + self._interrupt(connection, event["sequence"], "missing_response_id")
            if call.response_id is not None and call.response_id != response_id:
                return results + self._interrupt(connection, event["sequence"], "ambiguous_response_order")
            call.response_id = response_id
        if call.response_id is None:
            return results + self._interrupt(connection, event["sequence"], "missing_response_created")
        if response_id is not None and response_id != call.response_id:
            return results + self._interrupt(connection, event["sequence"], "response_id_mismatch")
        call.messages.append(self._evidence(event))
        if event_type == "response.output_item.done":
            output_index = value.get("output_index")
            item = value.get("item")
            if type(output_index) is int and output_index >= 0 and isinstance(item, dict):
                if output_index in call.output_items and call.output_items[output_index] != item:
                    call.conflicting_output_indices.add(output_index)
                if output_index not in call.conflicting_output_indices:
                    call.output_items[output_index] = item
        if event_type not in {"response.completed", "response.failed", "response.incomplete"}:
            return results
        if response_id != call.response_id:
            return results + self._interrupt(connection, event["sequence"], "missing_terminal_response_id")
        queue.popleft()
        results.append(self._response(call, event["sequence"], response, event_type.split(".")[1]))
        if event_type == "response.completed":
            if response_id in self.completed:
                self.completed[response_id] = None  # Duplicate IDs cannot establish unique lineage.
            else:
                self.completed[response_id] = call.snapshot
            parsed = parse_codex_message("server_to_client", raw)
            usage = parsed["usage"] if parsed else {}
            used = usage.get("input_tokens")
            results.append({
                "kind": "context.usage", "occurred_at": event.get("occurred_at"), "provider": "codex", "flow_id": call.snapshot.flow_id,
                "sequence": event["sequence"], "stream_identity": call.snapshot.stream_identity,
                "used_input_tokens": used, "components": usage,
                **usage_window(call.snapshot.exact_request, used, self.catalog, self.window, self.window_source),
                "usage_source": "wire_response_completed_usage" if used is not None else "usage_not_reported",
            })
        return results

    @staticmethod
    def _evidence(event: dict) -> dict:
        return {"event_id": event["event_id"], "sequence": event["sequence"], **event["payload"]}

    @staticmethod
    def _snapshot(event: dict, value: dict, *, http_request: dict | None = None) -> ContextSnapshot:
        blocks = []
        for name in ("instructions", "tools", "input"):
            if name not in value:
                continue
            items = value[name] if isinstance(value[name], list) else [value[name]]
            for i, item in enumerate(items):
                encoded = canonical(item)
                blocks.append(ContextBlock(
                    path=f"{name}/{i}" if isinstance(value[name], list) else name,
                    category=name, role=item.get("role") if isinstance(item, dict) else None,
                    kind=str(item.get("type", "object")) if isinstance(item, dict) else type(item).__name__,
                    value=item, fingerprint=hashlib.sha256(encoded).hexdigest(), byte_count=len(encoded),
                    origin="wire_request_field", origin_confidence="high", origin_evidence=(f"field:{name}",),
                ))
        call_id = event["flow_id"] if http_request is not None else f'{event["flow_id"]}~{event["payload"]["message_index"]}'
        body = http_request["body"] if http_request is not None else event["payload"]["body"]
        exact_request = {"transport": "http", **http_request} if http_request is not None else {
            "transport": "websocket", "connection_flow_id": event["flow_id"],
            "message_index": event["payload"]["message_index"], "body": body}
        identity = {"stream_id": f"codex:unclassified:{call_id}", "classification": "unclassified",
                    "confidence": "none", "evidence": ["no_stable_agent_identifier"],
                    "session_id_hint": None, "heuristic_signals": {}}
        return ContextSnapshot(
            flow_id=call_id, sequence=event["sequence"], body_byte_count=body["wire"]["byte_length"],
            token_count=None, token_count_source=None, fingerprint=hashlib.sha256(canonical(value)).hexdigest(),
            message_count=len(value["input"]) if isinstance(value.get("input"), list) else int("input" in value),
            blocks=tuple(blocks), exact_request=exact_request,
            stream_identity=identity,
            request_purpose={"classification": "unclassified", "confidence": "none", "evidence": []},
            request_operation="responses_generation",
        )

    @staticmethod
    def _response(call: Call, sequence: int, response: dict, status: str) -> dict:
        blocks = []
        output = response.get("output")
        output_source = "terminal_response_output"
        if not isinstance(output, list):
            output = [item for index, item in sorted(call.output_items.items())
                      if index not in call.conflicting_output_indices]
            output_source = "observed_completed_output_items" if output else "not_reported"
        usage = response.get("usage")
        output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
        if type(output_tokens) is not int or output_tokens < 0:
            output_tokens = None
        for item in output:
            if isinstance(item, dict) and item.get("type") == "message" and isinstance(item.get("content"), list):
                for part in item["content"]:
                    if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        blocks.append({"type": "text", "text": part["text"]})
                    else:
                        blocks.append({"type": "observed_item", "value": part})
            else:
                blocks.append({"type": "observed_item", "value": item})
        return {
            "kind": "context.response", "provider": "codex", "flow_id": call.snapshot.flow_id,
            "sequence": sequence, "stream_identity": call.snapshot.stream_identity,
            "response": {"model": response.get("model"), "message_id": call.response_id,
                         "stop_reason": status, "output_tokens": output_tokens, "content_blocks": blocks,
                         "output_source": output_source,
                         "conflicting_output_indices": sorted(call.conflicting_output_indices)},
            "purpose": {"classification": "unclassified", "confidence": "none", "evidence": []},
            "correlation": {"basis": "response_created_lane_order_then_response_id", "confidence": "medium" if call.response_id else "none"},
            "exact_response": {"transport": "websocket", "messages": list(call.messages)},
        }

    def _interrupt(self, connection: str | None, sequence: int, reason: str) -> list[dict]:
        results = []
        for key in list(self.pending):
            if connection is None or key[0] == connection:
                for call in self.pending.pop(key):
                    results.append(self._response(call, sequence, {}, reason))
        return results
