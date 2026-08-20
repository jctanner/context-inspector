"""FastAPI application exposing PTY-backed Claude terminal sessions."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .terminal import TerminalExit, TerminalManager
from .flows import FlowEventStream
from .context import ContextEventStream


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

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await manager.stop_all()

    app = FastAPI(title="Context Inspector", lifespan=lifespan)
    app.state.settings = settings
    app.state.terminals = manager

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/sessions", response_model=CreateSessionResponse)
    async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
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

    @app.delete("/api/sessions/{session_id}")
    async def stop_session(session_id: str) -> dict[str, bool]:
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

    @app.websocket("/api/sessions/{session_id}/contexts")
    async def context_socket(websocket: WebSocket, session_id: str, after_sequence: int = 0) -> None:
        if manager.get(session_id) is None:
            await websocket.close(code=4404, reason="Session not found")
            return
        await websocket.accept()
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
