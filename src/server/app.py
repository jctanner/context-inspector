"""FastAPI application exposing PTY-backed Claude terminal sessions."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .terminal import TerminalExit, TerminalManager
from .flows import FlowEventStream
from .context import ContextEventStream
from .context_index import ContextIndex
from .memory import get_memory


class CreateSessionRequest(BaseModel):
    extra_args: list[str] = Field(default_factory=list, max_length=32)


class CreateSessionResponse(BaseModel):
    session_id: str
    pid: int


class SessionStatusResponse(BaseModel):
    session_id: str
    pid: int
    alive: bool


def apply_terminal_message(session, message: object) -> str | None:
    """Apply one browser control message and return a safe error, if any."""

    if not isinstance(message, dict):
        return "terminal message must be an object"
    message_type = message.get("type")
    if message_type == "input":
        data = message.get("data")
        if not isinstance(data, str):
            return "input.data must be a string"
        session.write(data.encode("utf-8"))
        return None
    if message_type == "resize":
        try:
            session.resize(int(message.get("rows")), int(message.get("cols")))
        except (TypeError, ValueError) as exc:
            return str(exc)
        return None
    return "unsupported terminal message"


def create_app(*, settings: Settings | None = None, manager: TerminalManager | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    settings.validate()
    manager = manager or TerminalManager()
    indexes: dict[str, ContextIndex] = {}

    def context_index(session_id: str) -> ContextIndex:
        if manager.get(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session_id not in indexes:
            indexes[session_id] = ContextIndex(ContextEventStream(
                settings.state_dir / "sessions" / session_id / "events.jsonl", session_id,
                settings.context_window_tokens, settings.context_window_source,
            ))
        return indexes[session_id]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await asyncio.gather(*(index.close() for index in indexes.values()))
        await manager.stop_all()

    app = FastAPI(title="Context Inspector", lifespan=lifespan)
    app.state.settings = settings
    app.state.terminals = manager

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/sessions", response_model=CreateSessionResponse)
    async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        # No await between checking and creating: concurrent requests handled
        # by this server's event loop cannot spawn duplicate shared sessions.
        active = manager.active()
        if active is not None:
            return CreateSessionResponse(session_id=active.id, pid=active.pid)
        if any("\x00" in argument for argument in request.extra_args):
            raise HTTPException(status_code=400, detail="Arguments may not contain NUL bytes")
        try:
            argv = settings.claude_command(tuple(request.extra_args))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session_id = f"session-{uuid.uuid4().hex}"
        sessions_dir = settings.state_dir / "sessions"
        sessions_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        sessions_dir.chmod(0o700)
        event_dir = sessions_dir / session_id
        event_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        event_file = event_dir / "events.jsonl"
        environment = os.environ.copy()
        environment["CONTEXT_INSPECTOR_SESSION_ID"] = session_id
        environment["CONTEXT_INSPECTOR_EVENT_FILE"] = str(event_file)
        environment["CONTEXT_INSPECTOR_STATE_DIR"] = str(settings.state_dir)
        session = manager.create(argv, cwd=settings.workspace, env=environment, session_id=session_id)
        return CreateSessionResponse(session_id=session.id, pid=session.pid)

    @app.get("/api/sessions/active", response_model=SessionStatusResponse | None)
    async def active_session() -> SessionStatusResponse | None:
        session = manager.active()
        if session is None:
            return None
        return SessionStatusResponse(session_id=session.id, pid=session.pid, alive=True)

    @app.delete("/api/sessions/{session_id}")
    async def stop_session(session_id: str) -> dict[str, bool]:
        index = indexes.pop(session_id, None)
        if index is not None:
            await index.close()
        stopped = await manager.stop(session_id)
        if not stopped:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"stopped": True}

    @app.get("/api/sessions/{session_id}", response_model=SessionStatusResponse)
    async def session_status(session_id: str) -> SessionStatusResponse:
        session = manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionStatusResponse(session_id=session.id, pid=session.pid, alive=session.alive)

    @app.websocket("/api/sessions/{session_id}/terminal")
    async def terminal_socket(websocket: WebSocket, session_id: str) -> None:
        session = manager.get(session_id)
        if session is None:
            await websocket.close(code=4404, reason="Session not found")
            return
        await websocket.accept()
        output = session.subscribe()

        async def send_output() -> None:
            while True:
                message = await output.get()
                if isinstance(message, TerminalExit):
                    await websocket.send_text(json.dumps({"type": "exit", "exit_code": message.exit_code}))
                    return
                await websocket.send_bytes(message)

        async def receive_input() -> None:
            while True:
                message = await websocket.receive_json()
                error = apply_terminal_message(session, message)
                if error is not None:
                    await websocket.send_json({"type": "error", "message": error})

        sender = asyncio.create_task(send_output())
        receiver = asyncio.create_task(receive_input())
        try:
            done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        finally:
            for task in (sender, receiver):
                if not task.done():
                    task.cancel()
            await asyncio.gather(sender, receiver, return_exceptions=True)
            session.unsubscribe(output)

    @app.websocket("/api/sessions/{session_id}/flows")
    async def flow_socket(websocket: WebSocket, session_id: str, after_sequence: int = 0) -> None:
        if manager.get(session_id) is None:
            await websocket.close(code=4404, reason="Session not found")
            return
        await websocket.accept()
        stream = FlowEventStream(settings.state_dir / "sessions" / session_id / "events.jsonl", session_id)
        try:
            async for event in stream.events(after_sequence):
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass

    @app.get("/api/sessions/{session_id}/context-history")
    async def context_history(session_id: str, response: Response, before: int | None = None,
                              after_sequence: int = 0, limit: int = Query(default=25, ge=1, le=100)):
        index = context_index(session_id)
        await index.ready.wait()
        response.headers["Cache-Control"] = "no-store"
        return index.snapshot(before=before, after_sequence=after_sequence, limit=limit)

    async def memory_result(session_id: str, response: Response, path: str | None = None):
        response.headers["Cache-Control"] = "no-store"
        active = manager.active()
        if active is None or active.id != session_id:
            raise HTTPException(404, "No active Claude session", headers={"Cache-Control": "no-store"})
        try:
            result = await asyncio.to_thread(get_memory, session_id, path)
        except HTTPException as exc:
            exc.headers = {"Cache-Control": "no-store"}
            raise
        if manager.active() is not active:
            raise HTTPException(409, "Active session changed; refresh memory", headers={"Cache-Control": "no-store"})
        return result

    @app.get("/api/sessions/{session_id}/memory")
    async def memory_list(session_id: str, response: Response):
        return await memory_result(session_id, response)

    @app.get("/api/sessions/{session_id}/memory/file")
    async def memory_file(session_id: str, response: Response, path: str = Query(max_length=2048)):
        return await memory_result(session_id, response, path)

    @app.get("/api/sessions/{session_id}/context-details/{flow_id}/{part}")
    async def context_details(session_id: str, flow_id: str, part: str, response: Response):
        index = context_index(session_id)
        await index.ready.wait()
        kind = {"request": "context.diff", "response": "context.response"}.get(part)
        event = index.full.get((flow_id, kind))
        if event is None:
            raise HTTPException(status_code=404, detail="Captured detail not available")
        response.headers["Cache-Control"] = "no-store"
        return event

    @app.websocket("/api/sessions/{session_id}/contexts")
    async def context_socket(websocket: WebSocket, session_id: str, after_sequence: int = 0,
                             compact: bool = False, cursor: int = 0) -> None:
        if manager.get(session_id) is None:
            await websocket.close(code=4404, reason="Session not found")
            return
        await websocket.accept()
        if compact:
            index = context_index(session_id)
            await index.ready.wait()
            if cursor < 0 or cursor > len(index.journal):
                await websocket.close(code=4400, reason="Invalid context cursor")
                return
            try:
                while manager.get(session_id) is not None:
                    batch = index.journal[cursor:cursor + 100]
                    cursor += len(batch)
                    events = [event for event in batch if event["sequence"] > after_sequence]
                    await websocket.send_json({"type": "context-batch", "events": events, "cursor": cursor, "error": index.error})
                    await asyncio.sleep(0.25 if not batch else 0)
            except (WebSocketDisconnect, RuntimeError):
                pass
            return
        stream = ContextEventStream(
            settings.state_dir / "sessions" / session_id / "events.jsonl", session_id,
            settings.context_window_tokens, settings.context_window_source,
        )
        try:
            async for event in stream.events(after_sequence):
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass

    web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="web-assets")

        @app.get("/", include_in_schema=False)
        async def web_index() -> FileResponse:
            return FileResponse(web_dist / "index.html")

    return app
