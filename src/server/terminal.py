"""PTY-backed terminal sessions suitable for a WebSocket bridge."""

from __future__ import annotations

import asyncio
import contextlib
import os
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ptyprocess import PtyProcess


@dataclass(frozen=True)
class TerminalExit:
    exit_code: int | None


TerminalMessage = bytes | TerminalExit


class TerminalSession:
    """Own one child PTY and fan its unmodified output out to subscribers."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        rows: int = 50,
        cols: int = 200,
        replay_chunks: int = 256,
        session_id: str | None = None,
    ) -> None:
        if not argv:
            raise ValueError("argv must not be empty")
        self.id = session_id or f"session-{uuid.uuid4().hex}"
        self.argv = tuple(argv)
        self.cwd = Path(cwd)
        self.rows = rows
        self.cols = cols
        self._loop = asyncio.get_running_loop()
        self._child = PtyProcess.spawn(
            list(self.argv),
            cwd=str(self.cwd),
            env=dict(env or os.environ),
            dimensions=(rows, cols),
        )
        self._history: deque[bytes] = deque(maxlen=replay_chunks)
        self._subscribers: set[asyncio.Queue[TerminalMessage]] = set()
        self._closed = False
        self._exit = asyncio.Event()
        self._pump_thread = threading.Thread(target=self._pump, name=f"pty-{self.id}", daemon=True)
        self._pump_thread.start()

    @property
    def pid(self) -> int:
        return self._child.pid

    @property
    def alive(self) -> bool:
        return not self._closed and self._child.isalive()

    def subscribe(self, *, queue_size: int = 512) -> asyncio.Queue[TerminalMessage]:
        queue: asyncio.Queue[TerminalMessage] = asyncio.Queue(maxsize=queue_size)
        for chunk in self._history:
            if not queue.full():
                queue.put_nowait(chunk)
        if self._exit.is_set() and not queue.full():
            queue.put_nowait(TerminalExit(self._child.exitstatus))
        else:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TerminalMessage]) -> None:
        self._subscribers.discard(queue)

    def write(self, data: bytes) -> None:
        if not self.alive:
            raise RuntimeError("terminal session is not running")
        os.write(self._child.fd, data)

    def resize(self, rows: int, cols: int) -> None:
        if not (2 <= rows <= 1000 and 2 <= cols <= 1000):
            raise ValueError("terminal dimensions must be between 2 and 1000")
        self._child.setwinsize(rows, cols)
        self.rows = rows
        self.cols = cols

    async def close(self, *, graceful_timeout: float = 3.0) -> None:
        if self._closed:
            return
        if self._child.isalive():
            with contextlib.suppress(Exception):
                os.write(self._child.fd, b"\x03")
            await asyncio.sleep(0.1)
            if self._child.isalive():
                with contextlib.suppress(Exception):
                    os.write(self._child.fd, b"/exit\r")
            try:
                await asyncio.wait_for(self._exit.wait(), timeout=graceful_timeout)
            except TimeoutError:
                await asyncio.to_thread(self._child.terminate, True)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._exit.wait(), timeout=1.0)
        self._closed = True
        self._exit.set()
        if self._pump_thread.is_alive():
            await asyncio.to_thread(self._pump_thread.join, 1.0)

    def _pump(self) -> None:
        try:
            while True:
                chunk = self._child.read(65536)
                if chunk:
                    self._loop.call_soon_threadsafe(self._publish_chunk, chunk)
        except (EOFError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                self._child.wait()
            self._loop.call_soon_threadsafe(self._publish_exit)

    def _publish_chunk(self, chunk: bytes) -> None:
        self._history.append(chunk)
        for queue in tuple(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(chunk)

    def _publish_exit(self) -> None:
        self._exit.set()
        message = TerminalExit(self._child.exitstatus)
        for queue in tuple(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(message)


class TerminalManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    def create(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None, session_id: str | None = None) -> TerminalSession:
        session = TerminalSession(argv, cwd=cwd, env=env, session_id=session_id)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    async def stop(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        await session.close()
        return True

    async def stop_all(self) -> None:
        sessions = list(self._sessions.values())
        self._sessions.clear()
        await asyncio.gather(*(session.close() for session in sessions), return_exceptions=True)
