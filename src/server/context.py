"""Evidence-aware normalization and structural comparison of model requests."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import asyncio
import re
import zlib
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from src.protocol.events import ProtocolError, validate_event
from src.server.identity import classify_request_stream


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ContextBlock:
    path: str
    category: str
    role: str | None
    kind: str
    value: Any
    fingerprint: str
    byte_count: int
    origin: str
    origin_confidence: str
    origin_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ContextSnapshot:
    flow_id: str
    sequence: int
    body_byte_count: int
    token_count: int | None
    token_count_source: str | None
    fingerprint: str
    message_count: int
    blocks: tuple[ContextBlock, ...]
    exact_request: dict[str, Any]
    stream_identity: dict[str, Any]
    request_purpose: dict[str, Any]


def _content_blocks(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [{"type": "text", "text": value}] if isinstance(value, str) else [value]


def _instruction_strings(payload: dict[str, Any]) -> list[str]:
    """Return strings from instruction-bearing fields, excluding tool schemas."""

    strings: list[str] = []
    stack = [payload.get("system"), payload.get("messages")]
    while stack:
        value = stack.pop()
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return strings


def classify_request_purpose(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify only supported internal request shapes; otherwise abstain."""

    messages = payload.get("messages")
    if payload.get("max_tokens") == 1 and isinstance(messages, list) and len(messages) == 1:
        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        if content == "count" or content == [{"type": "text", "text": "count"}]:
            return {
                "classification": "likely_internal_token_counting", "confidence": "medium",
                "evidence": ["max_tokens_equals_one", "single_user_message_equals_count"],
            }
    title_instruction = not payload.get("tools") and any(
        re.search(r"(?:generate|create|write|provide).{0,100}(?:conversation |chat )?title|title.{0,60}(?:conversation|chat)", value, re.IGNORECASE | re.DOTALL)
        for value in _instruction_strings(payload)
    )
    if title_instruction:
        return {
            "classification": "likely_internal_title_generation", "confidence": "medium",
            "evidence": ["instruction_content_requests_title", "request_has_no_tools"],
        }
    return {"classification": "unclassified", "confidence": "none", "evidence": ["no_supported_request_purpose_pattern"]}


def classify_block_origin(value: Any) -> tuple[str, str, tuple[str, ...]]:
    text = value.get("text") if isinstance(value, dict) else None
    if isinstance(text, str) and text.lstrip().startswith("<system-reminder>"):
        return "harness_injected_system_reminder", "medium", ("system_reminder_wrapper",)
    if isinstance(text, str) and text.lstrip().startswith(("<command-name>", "<command-message>", "<local-command-stdout>", "<local-command-caveat>")):
        return "harness_injected_local_command", "medium", ("local_command_wrapper",)
    return "unclassified_request_content", "none", ("no_supported_origin_marker",)


def comparison_lineage(snapshot: ContextSnapshot) -> str:
    classification = snapshot.request_purpose["classification"]
    if classification.startswith("likely_internal_"):
        return f'{snapshot.stream_identity["stream_id"]}:purpose:{classification}'
    return snapshot.stream_identity["stream_id"]


def _token_count(payload: dict[str, Any]) -> tuple[int | None, str | None]:
    candidates = [
        (payload.get("input_tokens"), "input_tokens"),
        (payload.get("token_count"), "token_count"),
        ((payload.get("usage") or {}).get("input_tokens") if isinstance(payload.get("usage"), dict) else None, "usage.input_tokens"),
    ]
    for value, source in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value, source
    return None, None


def normalize_request(event: dict[str, Any]) -> ContextSnapshot | None:
    """Return a model-context snapshot or None for non-model HTTP requests."""

    if event.get("kind") != "request.started":
        return None
    request = event.get("payload", {}).get("request", {})
    body = request.get("body", {})
    decoded = body.get("decoded")
    if not isinstance(decoded, dict) or decoded.get("kind") != "json":
        return None
    payload = decoded.get("value")
    if not isinstance(payload, dict) or not any(key in payload for key in ("messages", "system", "tools")):
        return None

    blocks: list[ContextBlock] = []

    def add(path: str, category: str, role: str | None, kind: str, value: Any) -> None:
        encoded = _canonical(value)
        origin, confidence, evidence = classify_block_origin(value)
        blocks.append(ContextBlock(path, category, role, kind, value, hashlib.sha256(encoded).hexdigest(), len(encoded), origin, confidence, evidence))

    for index, value in enumerate(_content_blocks(payload.get("system", []))):
        kind = value.get("type", "object") if isinstance(value, dict) else type(value).__name__
        add(f"system/{index}", "system", None, str(kind), value)
    for index, tool in enumerate(payload.get("tools") or []):
        name = tool.get("name", f"tool-{index}") if isinstance(tool, dict) else f"tool-{index}"
        add(f"tools/{index}", "tools", None, str(name), tool)
    messages = payload.get("messages") or []
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            add(f"messages/{message_index}/0", "messages", None, type(message).__name__, message)
            continue
        role = str(message.get("role", "unknown"))
        for block_index, value in enumerate(_content_blocks(message.get("content"))):
            kind = value.get("type", "object") if isinstance(value, dict) else type(value).__name__
            add(f"messages/{message_index}/{block_index}", "messages", role, str(kind), value)

    wire = body.get("wire") or {}
    body_bytes = wire.get("byte_length") if isinstance(wire.get("byte_length"), int) else len(_canonical(payload))
    tokens, token_source = _token_count(payload)
    request_purpose = classify_request_purpose(payload)
    return ContextSnapshot(
        flow_id=event["flow_id"], sequence=event["sequence"], body_byte_count=body_bytes,
        token_count=tokens, token_count_source=token_source, fingerprint=_fingerprint(payload),
        message_count=len(messages), blocks=tuple(blocks), exact_request=request,
        stream_identity=classify_request_stream(request),
        request_purpose=request_purpose,
    )


def compare_snapshots(previous: ContextSnapshot | None, current: ContextSnapshot) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    if previous is None:
        for block in current.blocks:
            changes.append({"change": "added", "before": None, "after": asdict(block)})
        relationship = "initial"
    elif previous.fingerprint == current.fingerprint:
        relationship = "retry_or_duplicate"
        for block in current.blocks:
            changes.append({"change": "retained", "before": asdict(block), "after": asdict(block)})
    else:
        relationship = "compaction_candidate" if current.message_count < previous.message_count else "chronological"
        old = list(previous.blocks)
        new = list(current.blocks)
        used_old: set[int] = set()
        used_new: set[int] = set()

        old_exact = {(block.path, block.fingerprint): index for index, block in enumerate(old)}
        for new_index, block in enumerate(new):
            old_index = old_exact.get((block.path, block.fingerprint))
            if old_index is not None and old_index not in used_old:
                used_old.add(old_index); used_new.add(new_index)
                changes.append({"change": "retained", "before": asdict(old[old_index]), "after": asdict(block)})

        by_fingerprint: dict[str, deque[int]] = defaultdict(deque)
        for index, block in enumerate(old):
            if index not in used_old:
                by_fingerprint[block.fingerprint].append(index)
        for new_index, block in enumerate(new):
            if new_index in used_new or not by_fingerprint[block.fingerprint]:
                continue
            old_index = by_fingerprint[block.fingerprint].popleft()
            used_old.add(old_index); used_new.add(new_index)
            changes.append({"change": "retained", "before": asdict(old[old_index]), "after": asdict(block), "moved": True})

        old_by_path = {block.path: index for index, block in enumerate(old) if index not in used_old}
        for new_index, block in enumerate(new):
            if new_index in used_new:
                continue
            old_index = old_by_path.get(block.path)
            if old_index is not None and old_index not in used_old:
                used_old.add(old_index); used_new.add(new_index)
                changes.append({"change": "transformed", "before": asdict(old[old_index]), "after": asdict(block)})
        for index, block in enumerate(old):
            if index not in used_old:
                changes.append({"change": "removed", "before": asdict(block), "after": None})
        for index, block in enumerate(new):
            if index not in used_new:
                changes.append({"change": "added", "before": None, "after": asdict(block)})

    counts = {kind: sum(change["change"] == kind for change in changes) for kind in ("added", "removed", "retained", "transformed")}
    return {
        "kind": "context.diff", "flow_id": current.flow_id, "sequence": current.sequence,
        "predecessor_flow_id": previous.flow_id if previous else None,
        "predecessor_basis": (
            "recognized_request_purpose" if current.request_purpose["classification"].startswith("likely_internal_")
            else "stable_wire_agent_header" if current.stream_identity["confidence"] == "high"
            else "session_chronology_unclassified"
        ),
        "predecessor_confidence": (
            current.request_purpose["confidence"]
            if previous and current.request_purpose["classification"].startswith("likely_internal_")
            else current.stream_identity["confidence"] if previous else "none"
        ),
        "stream_identity": current.stream_identity,
        "request_purpose": current.request_purpose,
        "comparison_lineage": comparison_lineage(current),
        "relationship": relationship,
        "counts": counts,
        "metrics": {
            "body_bytes": current.body_byte_count,
            "previous_body_bytes": previous.body_byte_count if previous else None,
            "token_count": current.token_count,
            "token_count_source": current.token_count_source,
        },
        "changes": changes,
        "exact_request": current.exact_request,
    }


def derive_context_diffs(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    previous_by_stream: dict[str, ContextSnapshot] = {}
    for event in events:
        current = normalize_request(event)
        if current is None:
            continue
        stream_id = comparison_lineage(current)
        previous = previous_by_stream.get(stream_id)
        diff = compare_snapshots(previous, current)
        diffs.append(diff)
        if diff["relationship"] != "retry_or_duplicate":
            previous_by_stream[stream_id] = current
    return diffs


def extract_sse_usage(buffer: str) -> tuple[list[dict[str, int]], str]:
    """Extract complete Anthropic-style SSE usage objects, retaining a partial tail."""

    normalized = buffer.replace("\r\n", "\n")
    parts = normalized.split("\n\n")
    remainder = parts.pop()
    found: list[dict[str, int]] = []
    for part in parts:
        data = "\n".join(line[5:].lstrip() for line in part.splitlines() if line.startswith("data:"))
        if not data or data == "[DONE]":
            continue
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            continue
        stack = [value]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                usage = current.get("usage")
                if isinstance(usage, dict) and any(key in usage for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")):
                    found.append({key: int(usage.get(key, 0) or 0) for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")})
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
    return found, remainder


def parse_sse_data(text: str) -> list[dict[str, Any]]:
    """Parse complete JSON SSE data records, ignoring transport framing."""

    records: list[dict[str, Any]] = []
    for part in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in part.splitlines() if line.startswith("data:"))
        if not data or data == "[DONE]":
            continue
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def reconstruct_sse_response(text: str) -> dict[str, Any]:
    """Build semantic response blocks from complete SSE records."""

    model = None
    message_id = None
    stop_reason = None
    output_tokens = None
    blocks: dict[int, dict[str, Any]] = {}
    partial_json: dict[int, str] = defaultdict(str)
    for record in parse_sse_data(text):
        record_type = record.get("type")
        if record_type == "message_start" and isinstance(record.get("message"), dict):
            message = record["message"]
            model = message.get("model")
            message_id = message.get("id")
        elif record_type == "content_block_start" and isinstance(record.get("index"), int):
            block = record.get("content_block")
            blocks[record["index"]] = dict(block) if isinstance(block, dict) else {"value": block}
        elif record_type == "content_block_delta" and isinstance(record.get("index"), int):
            index = record["index"]
            delta = record.get("delta")
            if not isinstance(delta, dict):
                continue
            block = blocks.setdefault(index, {"type": "unknown"})
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                block["text"] = str(block.get("text", "")) + str(delta.get("text", ""))
            elif delta_type == "thinking_delta":
                block["thinking"] = str(block.get("thinking", "")) + str(delta.get("thinking", ""))
            elif delta_type == "signature_delta":
                block["signature"] = str(block.get("signature", "")) + str(delta.get("signature", ""))
            elif delta_type == "input_json_delta":
                partial_json[index] += str(delta.get("partial_json", ""))
        elif record_type == "message_delta":
            delta = record.get("delta")
            if isinstance(delta, dict):
                stop_reason = delta.get("stop_reason", stop_reason)
            usage = record.get("usage")
            if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int):
                output_tokens = usage["output_tokens"]
    for index, value in partial_json.items():
        try:
            blocks.setdefault(index, {"type": "tool_use"})["input"] = json.loads(value)
        except json.JSONDecodeError:
            blocks.setdefault(index, {"type": "tool_use"})["partial_input_json"] = value
    return {
        "model": model, "message_id": message_id, "stop_reason": stop_reason,
        "output_tokens": output_tokens, "content_blocks": [blocks[index] for index in sorted(blocks)],
    }


def classify_response_purpose(snapshot: ContextSnapshot, response: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative inferred purpose; never infer primary by absence."""

    blocks = response.get("content_blocks")
    title_shape = False
    if isinstance(blocks, list) and len(blocks) == 1 and isinstance(blocks[0], dict):
        text = blocks[0].get("text")
        if isinstance(text, str):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
            try:
                value = json.loads(candidate)
                title_shape = isinstance(value, dict) and set(value) == {"title"} and isinstance(value["title"], str)
            except json.JSONDecodeError:
                pass

    title_instruction = snapshot.request_purpose["classification"] == "likely_internal_title_generation"
    if title_shape and title_instruction:
        return {
            "classification": "likely_internal_title_generation", "confidence": "medium",
            "evidence": ["request_contains_title_generation_instruction", "response_is_single_title_json_object"],
        }
    return {
        "classification": "unclassified", "confidence": "none",
        "evidence": ["no_stable_purpose_identifier"],
    }


def decode_response_bytes(raw: bytes, content_encoding: str) -> str | None:
    """Decode a complete captured response without treating chunks as documents."""

    try:
        encoding = content_encoding.lower()
        if encoding == "gzip":
            raw = gzip.decompress(raw)
        elif encoding == "deflate":
            raw = zlib.decompress(raw)
        elif encoding not in {"", "identity"}:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError, zlib.error):
        return None


class ContextEventStream:
    """Tail raw events while maintaining the comparison baseline for replay."""

    def __init__(self, path, session_id: str, context_window_tokens: int = 200_000, context_window_source: str = "configured default from experiment baseline") -> None:
        self.path = path
        self.session_id = session_id
        self.context_window_tokens = context_window_tokens
        self.context_window_source = context_window_source

    async def events(self, after: int = 0):
        offset = 0
        previous_by_stream: dict[str, ContextSnapshot] = {}
        request_by_flow: dict[str, ContextSnapshot] = {}
        sse_buffers: dict[str, str] = defaultdict(str)
        response_wire: dict[str, bytearray] = defaultdict(bytearray)
        response_encoding: dict[str, str] = {}
        response_content_type: dict[str, str] = {}
        response_metadata: dict[str, dict[str, Any]] = {}
        usage_emitted: set[str] = set()
        while True:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as source:
                    source.seek(offset)
                    while line := source.readline():
                        offset = source.tell()
                        try:
                            event = json.loads(line)
                            validate_event(event)
                            if event["session_id"] != self.session_id:
                                raise ProtocolError("event session_id does not match stream")
                        except (json.JSONDecodeError, ProtocolError) as exc:
                            yield {"type": "stream-error", "message": str(exc)}
                            continue
                        current = normalize_request(event)
                        if current is None:
                            kind = event.get("kind")
                            flow_id = event.get("flow_id")
                            if kind == "response.started" and flow_id in request_by_flow:
                                headers = event.get("payload", {}).get("headers", {})
                                normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
                                response_encoding[flow_id] = normalized_headers.get("content-encoding", "identity")
                                response_content_type[flow_id] = normalized_headers.get("content-type", "")
                                response_metadata[flow_id] = {
                                    "status_code": event.get("payload", {}).get("status_code"),
                                    "reason": event.get("payload", {}).get("reason"),
                                    "http_version": event.get("payload", {}).get("http_version"),
                                    "headers": headers,
                                }
                            if kind == "response.block" and flow_id in request_by_flow:
                                wire = event.get("payload", {}).get("body", {}).get("wire", {})
                                if wire.get("encoding") == "base64" and isinstance(wire.get("data"), str):
                                    try:
                                        response_wire[flow_id].extend(base64.b64decode(wire["data"], validate=True))
                                    except (ValueError, TypeError):
                                        pass
                                decoded = event.get("payload", {}).get("body", {}).get("decoded")
                                if isinstance(decoded, dict) and decoded.get("kind") == "sse" and isinstance(decoded.get("value"), str):
                                    usages, sse_buffers[flow_id] = extract_sse_usage(sse_buffers[flow_id] + decoded["value"])
                                    for usage in usages:
                                        usage_emitted.add(flow_id)
                                        total = sum(usage.values())
                                        snapshot = request_by_flow[flow_id]
                                        if event["sequence"] > after:
                                            yield {
                                                "kind": "context.usage", "flow_id": flow_id, "sequence": event["sequence"],
                                                "stream_identity": snapshot.stream_identity,
                                                "used_input_tokens": total, "components": usage,
                                                "context_window_tokens": self.context_window_tokens,
                                                "context_window_source": self.context_window_source,
                                                "percent": min(100.0, total / self.context_window_tokens * 100),
                                                "usage_source": "wire_response_sse_usage",
                                            }
                            if kind == "flow.completed" and flow_id in request_by_flow and flow_id not in usage_emitted:
                                if "event-stream" in response_content_type.get(flow_id, ""):
                                    text = decode_response_bytes(bytes(response_wire[flow_id]), response_encoding.get(flow_id, "identity"))
                                    if text is not None:
                                        usages, _ = extract_sse_usage(text + "\n\n")
                                        for usage in usages[:1]:
                                            total = sum(usage.values())
                                            snapshot = request_by_flow[flow_id]
                                            if event["sequence"] > after:
                                                yield {
                                                    "kind": "context.usage", "flow_id": flow_id, "sequence": event["sequence"],
                                                    "stream_identity": snapshot.stream_identity,
                                                    "used_input_tokens": total, "components": usage,
                                                    "context_window_tokens": self.context_window_tokens,
                                                    "context_window_source": self.context_window_source,
                                                    "percent": min(100.0, total / self.context_window_tokens * 100),
                                                    "usage_source": "wire_response_sse_usage_reassembled",
                                                }
                            if kind == "flow.completed" and flow_id in request_by_flow:
                                raw_response = bytes(response_wire[flow_id])
                                text = decode_response_bytes(raw_response, response_encoding.get(flow_id, "identity"))
                                if text is not None and "event-stream" in response_content_type.get(flow_id, ""):
                                    snapshot = request_by_flow[flow_id]
                                    reconstructed = reconstruct_sse_response(text)
                                    if event["sequence"] > after:
                                        yield {
                                            "kind": "context.response", "flow_id": flow_id, "sequence": event["sequence"],
                                            "stream_identity": snapshot.stream_identity,
                                            "response": reconstructed,
                                            "purpose": classify_response_purpose(snapshot, reconstructed),
                                            "exact_response": {
                                                **response_metadata.get(flow_id, {}),
                                                "body": {
                                                    "wire": {"encoding": "base64", "data": base64.b64encode(raw_response).decode("ascii"),
                                                             "byte_length": len(raw_response),
                                                             "content_encoding": response_encoding.get(flow_id, "identity")},
                                                    "decoded": {"kind": "sse", "value": text},
                                                    "decode_status": "decoded",
                                                },
                                            },
                                        }
                            if kind in {"flow.completed", "flow.error"} and isinstance(flow_id, str):
                                response_wire.pop(flow_id, None)
                                response_encoding.pop(flow_id, None)
                                response_content_type.pop(flow_id, None)
                                response_metadata.pop(flow_id, None)
                                sse_buffers.pop(flow_id, None)
                            continue
                        request_by_flow[current.flow_id] = current
                        stream_id = comparison_lineage(current)
                        previous = previous_by_stream.get(stream_id)
                        diff = compare_snapshots(previous, current)
                        if current.sequence > after:
                            yield diff
                        if diff["relationship"] != "retry_or_duplicate":
                            previous_by_stream[stream_id] = current
            await asyncio.sleep(0.05)
