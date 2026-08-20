from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import tempfile
from pathlib import Path
import unittest
import urllib.error
import urllib.request
import base64

import websockets
from src.proxy.live_capture import JsonlEmitter


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class LiveServerTests(unittest.TestCase):
    def test_real_http_websocket_pty_and_disconnect_cleanup(self) -> None:
        port = free_port()
        env = os.environ.copy()
        state_directory = tempfile.TemporaryDirectory()
        env["CONTEXT_INSPECTOR_STATE_DIR"] = state_directory.name
        env["CONTEXT_INSPECTOR_COMMAND_JSON"] = json.dumps([
            "/bin/sh", "-c", "stty -echo; printf '\\033[35mREADY\\033[0m\\n'; exec cat",
        ])
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.tests.asgi_fixture:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            health_url = f"http://127.0.0.1:{port}/api/health"
            for _ in range(50):
                try:
                    with urllib.request.urlopen(health_url, timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.05)
            else:
                self.fail("Uvicorn fixture did not become ready")

            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/sessions",
                data=b'{"extra_args":[]}',
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                session_id = json.load(response)["session_id"]

            asyncio.run(self._exercise_socket(port, session_id, state_directory.name))
            time.sleep(0.2)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/sessions/{session_id}", timeout=2) as response:
                status = json.load(response)
            self.assertTrue(status["alive"])
            asyncio.run(self._exercise_reconnect(port, session_id))
            delete = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/sessions/{session_id}", method="DELETE",
            )
            with urllib.request.urlopen(delete, timeout=2) as response:
                self.assertTrue(json.load(response)["stopped"])
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/sessions/{session_id}", timeout=2)
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 404)
                error.close()
            else:
                self.fail("Explicitly stopped session remained available")
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=2)
            state_directory.cleanup()

    async def _exercise_socket(self, port: int, session_id: str, state_directory: str) -> None:
        uri = f"ws://127.0.0.1:{port}/api/sessions/{session_id}/terminal"
        flow_uri = f"ws://127.0.0.1:{port}/api/sessions/{session_id}/flows?after_sequence=0"
        context_uri = f"ws://127.0.0.1:{port}/api/sessions/{session_id}/contexts?after_sequence=0"
        async with websockets.connect(uri) as websocket, websockets.connect(flow_uri) as flow_socket, websockets.connect(context_uri) as context_socket:
            initial = await asyncio.wait_for(websocket.recv(), timeout=2)
            self.assertIsInstance(initial, bytes)
            self.assertIn(b"\x1b[35mREADY\x1b[0m", initial)
            await websocket.send(json.dumps({"type": "input", "data": "hello live socket\n"}))
            output = await asyncio.wait_for(websocket.recv(), timeout=2)
            self.assertIsInstance(output, bytes)
            self.assertIn(b"hello live socket", output)
            await websocket.send(json.dumps({"type": "resize", "rows": 45, "cols": 140}))
            event_path = Path(state_directory) / "sessions" / session_id / "events.jsonl"
            emitter = JsonlEmitter(event_path, session_id)
            raw = b'{"messages":[{"role":"user","content":"context fixture"}]}'
            emitter.emit("request.started", "flow-context", {"request": {
                "method": "POST", "url": "https://api.anthropic.com/v1/messages", "http_version": "HTTP/2",
                "headers": {"content-type": "application/json"},
                "body": {"wire": {"encoding": "base64", "data": base64.b64encode(raw).decode(), "byte_length": len(raw), "content_encoding": "identity"},
                         "decoded": {"kind": "json", "value": json.loads(raw)}, "decode_status": "decoded"},
            }})
            raw_event = json.loads(await asyncio.wait_for(flow_socket.recv(), timeout=2))
            self.assertEqual(raw_event["kind"], "request.started")
            context_event = json.loads(await asyncio.wait_for(context_socket.recv(), timeout=2))
            self.assertEqual(context_event["kind"], "context.diff")
            self.assertEqual(context_event["relationship"], "initial")
            usage_sse = 'data: {"type":"message_start","message":{"usage":{"input_tokens":11,"cache_creation_input_tokens":22,"cache_read_input_tokens":33}}}\n\n'
            usage_raw = usage_sse.encode()
            emitter.emit("response.block", "flow-context", {
                "block_index": 0, "offset": 0, "final": False,
                "body": {"wire": {"encoding": "base64", "data": base64.b64encode(usage_raw).decode(), "byte_length": len(usage_raw), "content_encoding": "identity"},
                         "decoded": {"kind": "sse", "value": usage_sse}, "decode_status": "decoded"},
            })
            await asyncio.wait_for(flow_socket.recv(), timeout=2)
            usage_event = json.loads(await asyncio.wait_for(context_socket.recv(), timeout=2))
            self.assertEqual(usage_event["kind"], "context.usage")
            self.assertEqual(usage_event["flow_id"], "flow-context")
            self.assertEqual(usage_event["used_input_tokens"], 66)
            emitter.emit("flow.error", "flow-live", {
                "stage": "connect", "code": "fixture", "message": "safe fixture error",
                "retryable": False, "request_observed": False, "response_observed": False,
            })
            flow_event = json.loads(await asyncio.wait_for(flow_socket.recv(), timeout=2))
            self.assertEqual(flow_event["kind"], "flow.error")

    async def _exercise_reconnect(self, port: int, session_id: str) -> None:
        uri = f"ws://127.0.0.1:{port}/api/sessions/{session_id}/terminal"
        async with websockets.connect(uri) as websocket:
            replay = await asyncio.wait_for(websocket.recv(), timeout=2)
            self.assertIsInstance(replay, bytes)
            self.assertIn(b"READY", replay)
            await websocket.send(json.dumps({"type": "input", "data": "after reconnect\n"}))
            chunks = bytearray()
            while b"after reconnect" not in chunks:
                message = await asyncio.wait_for(websocket.recv(), timeout=2)
                if isinstance(message, bytes):
                    chunks.extend(message)
            self.assertIn(b"after reconnect", chunks)


if __name__ == "__main__":
    unittest.main()
