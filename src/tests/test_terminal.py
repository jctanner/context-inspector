from __future__ import annotations

import asyncio
import json
import os
import struct
import termios
import unittest

from src.server.config import DEFAULT_RUNNER, Settings
from src.server.terminal import TerminalExit, TerminalSession


async def bytes_until(queue: asyncio.Queue, marker: bytes, timeout: float = 2.0) -> bytes:
    chunks = bytearray()
    while True:
        message = await asyncio.wait_for(queue.get(), timeout=timeout)
        if isinstance(message, TerminalExit):
            return bytes(chunks)
        chunks.extend(message)
        if marker in chunks:
            return bytes(chunks)


class TerminalSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_input_output_and_ansi_are_preserved(self) -> None:
        command = ("/bin/sh", "-c", "stty -echo; printf '\\033[31mREADY\\033[0m\\n'; exec cat")
        session = TerminalSession(command, cwd=DEFAULT_RUNNER.parent)
        await asyncio.sleep(0.1)
        queue = session.subscribe()
        try:
            initial = await bytes_until(queue, b"READY")
            self.assertIn(b"\x1b[31mREADY\x1b[0m", initial)
            session.write(b"hello terminal\n")
            echoed = await bytes_until(queue, b"hello terminal")
            self.assertIn(b"hello terminal", echoed)
        finally:
            await session.close(graceful_timeout=0.2)

    async def test_resize_reaches_child_pty(self) -> None:
        session = TerminalSession(("/bin/sh", "-c", "sleep 30"), cwd=DEFAULT_RUNNER.parent)
        try:
            session.resize(42, 132)
            packed = struct.pack("HHHH", 0, 0, 0, 0)
            rows, cols, _, _ = struct.unpack("HHHH", __import__("fcntl").ioctl(session._child.fd, termios.TIOCGWINSZ, packed))
            self.assertEqual((rows, cols), (42, 132))
        finally:
            await session.close(graceful_timeout=0.1)

    async def test_close_terminates_uncooperative_child(self) -> None:
        session = TerminalSession(("/bin/sh", "-c", "trap '' INT TERM; while :; do sleep 1; done"), cwd=DEFAULT_RUNNER.parent)
        await session.close(graceful_timeout=0.1)
        self.assertFalse(session.alive)


class SettingsTests(unittest.TestCase):
    def test_default_server_is_loopback_and_runner_is_real(self) -> None:
        settings = Settings()
        settings.validate()
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertTrue(DEFAULT_RUNNER.is_file())
        self.assertTrue(os.access(DEFAULT_RUNNER, os.X_OK))
        self.assertEqual(settings.claude_command()[:3], (str(DEFAULT_RUNNER), "--", "claude"))

    def test_non_loopback_binding_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            Settings(host="0.0.0.0").validate()

    def test_context_window_is_configurable_and_must_be_positive(self) -> None:
        previous = os.environ.get("CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS")
        os.environ["CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS"] = "1000000"
        try:
            settings = Settings.from_environment()
            self.assertEqual(settings.context_window_tokens, 1_000_000)
            self.assertEqual(settings.context_window_source, "environment override")
        finally:
            if previous is None:
                os.environ.pop("CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS", None)
            else:
                os.environ["CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS"] = previous
        with self.assertRaisesRegex(ValueError, "must be positive"):
            Settings(context_window_tokens=0).validate()

    def test_environment_command_override_is_an_argument_vector(self) -> None:
        previous = os.environ.get("CONTEXT_INSPECTOR_COMMAND_JSON")
        os.environ["CONTEXT_INSPECTOR_COMMAND_JSON"] = json.dumps(["/bin/echo", "safe value"])
        try:
            settings = Settings.from_environment()
            self.assertEqual(settings.claude_command(), ("/bin/echo", "safe value"))
            with self.assertRaisesRegex(ValueError, "extra_args"):
                settings.claude_command(("unexpected",))
        finally:
            if previous is None:
                os.environ.pop("CONTEXT_INSPECTOR_COMMAND_JSON", None)
            else:
                os.environ["CONTEXT_INSPECTOR_COMMAND_JSON"] = previous


if __name__ == "__main__":
    unittest.main()
