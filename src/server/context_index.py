"""One derived-context scan per session; compact history and lazy evidence."""
from __future__ import annotations

import asyncio
import hashlib
import json
from urllib.parse import quote

from .context import ContextEventStream


class ContextIndex:
    def __init__(self, stream: ContextEventStream):
        self.stream = stream
        self.ready = asyncio.Event()
        self.journal: list[dict] = []
        self.requests: list[str] = []
        self.full: dict[tuple[str, str], dict] = {}
        self.latest: dict[tuple[str, str], dict] = {}
        self.error: str | None = None
        self.task = asyncio.create_task(self._consume())

    async def _consume(self):
        try:
            async for event in self.stream.events(mark_ready=True):
                if event.get("type") == "replay-ready":
                    self.ready.set()
                    continue
                if "kind" not in event:
                    self.error = "A capture record could not be interpreted"
                    continue
                self.add(event)
        except Exception:
            self.error = "Context indexing stopped; reconnect after checking the server"
        finally:
            self.ready.set()

    def add(self, event: dict):
        kind, flow = event["kind"], event["flow_id"]
        key = (flow, kind)
        self.full[key] = event
        summary = dict(event)
        detail = f"/api/sessions/{quote(self.stream.session_id, safe='')}/context-details/{quote(flow, safe='')}"
        if kind == "context.diff":
            if flow not in self.requests:
                self.requests.append(flow)
            summary["request_number"] = self.requests.index(flow) + 1
            summary["changes"] = []
            summary["exact_request"] = {}
            summary["detail_url"] = detail + "/request"
            body = event["exact_request"].get("body", {}).get("decoded", {}).get("value")
            summary["body_digest"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if body is not None else ""
        elif kind == "context.response":
            summary["exact_response"] = {}
            summary["detail_url"] = detail + "/response"
            text = "\n\n".join(block.get("text", "") for block in event["response"]["content_blocks"] if block.get("type") == "text")
            summary["response"] = {**event["response"], "content_blocks": [{"type": "text", "text": text[:500] + ("…" if len(text) > 500 else "")}] if text else []}
        summary["cursor"] = len(self.journal) + 1
        self.journal.append(summary)
        self.latest[key] = summary

    def snapshot(self, *, before: int | None = None, after_sequence: int = 0, limit: int = 25):
        eligible = [flow for flow in self.requests if self.latest[(flow, "context.diff")]["sequence"] > after_sequence]
        older = [flow for flow in eligible if before is None or self.latest[(flow, "context.diff")]["request_number"] < before]
        selected = older[-limit:]
        events = [self.latest[(flow, kind)] for flow in selected for kind in ("context.diff", "context.usage", "context.response") if (flow, kind) in self.latest]
        usage = None
        for flow in eligible:
            purpose = self.latest.get((flow, "context.response"), {}).get("purpose", {}).get("classification", "")
            request_purpose = self.latest[(flow, "context.diff")]["request_purpose"]["classification"]
            candidate = self.latest.get((flow, "context.usage"))
            if candidate and not purpose.startswith("likely_internal_") and not request_purpose.startswith("likely_internal_"):
                if usage is None or candidate["sequence"] > usage["sequence"]:
                    usage = candidate
        return {"events": events, "cursor": len(self.journal), "total": len(eligible),
                "next_before": self.latest[(selected[0], "context.diff")]["request_number"] if selected and len(older) > len(selected) else None,
                "latest_usage": usage, "error": self.error}

    async def close(self):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
