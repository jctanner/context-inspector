"""Tail and replay per-session live proxy events."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.protocol.events import ProtocolError, validate_event


class FlowEventStream:
    def __init__(self, path: Path, session_id: str) -> None:
        self.path = path
        self.session_id = session_id

    async def events(self, after: int = 0):
        offset = 0
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
                        if event["sequence"] > after:
                            yield event
            await asyncio.sleep(0.05)
