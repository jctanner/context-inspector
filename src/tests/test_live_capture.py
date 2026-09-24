from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.protocol.events import validate_event
from src.proxy.live_capture import JsonlEmitter, LiveCapture, _body, _selected


class Headers(dict):
    def items(self, multi=False):
        return super().items()


def flow(flow_id="flow-1", response_body=b'data: {"type":"done"}\n\n'):
    request = SimpleNamespace(
        method="POST", pretty_url="https://api.anthropic.com/v1/messages",
        pretty_host="api.anthropic.com", http_version="HTTP/2.0",
        headers=Headers({"content-type": "application/json", "Authorization": "secret"}),
        raw_content=b'{"messages":[]}',
    )
    response = SimpleNamespace(
        status_code=200, reason="OK", http_version="HTTP/2.0",
        headers=Headers({"content-type": "text/event-stream", "set-cookie": "secret"}),
        raw_content=response_body, stream=None,
    )
    return SimpleNamespace(id=flow_id, request=request, response=response, error=None)


class LiveCaptureTests(unittest.TestCase):
    def test_auth_and_unknown_provider_urls_are_excluded_before_capture(self) -> None:
        auth_urls = (
            "https://oauth2.googleapis.com/token",
            "https://accounts.google.com/o/oauth2/token",
            "https://api.anthropic.com/oauth/token",
            "https://api.anthropic.com/v1/messages?access_token=synthetic-secret",
            "https://api.anthropic.com/v1/unknown",
        )
        for url in auth_urls:
            item = flow()
            item.request.pretty_url = url
            item.request.pretty_host = url.split("/", 3)[2].split(":")[0]
            with self.subTest(url=url):
                self.assertFalse(_selected(item))

    def test_only_known_anthropic_and_vertex_model_operations_are_selected(self) -> None:
        item = flow()
        self.assertTrue(_selected(item))
        item.request.pretty_host = "us-east5-aiplatform.googleapis.com"
        item.request.pretty_url = "https://us-east5-aiplatform.googleapis.com/v1/projects/p/locations/us-east5/publishers/anthropic/models/claude-sonnet:streamRawPredict"
        self.assertTrue(_selected(item))
        item.request.pretty_url = "https://oauth2.googleapis.com/token"
        item.request.pretty_host = "oauth2.googleapis.com"
        self.assertFalse(_selected(item))

    def test_excluded_oauth_exchange_never_emits_or_archives_synthetic_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
            item = flow()
            item.request.pretty_url = "https://oauth2.googleapis.com/token"
            item.request.pretty_host = "oauth2.googleapis.com"
            item.request.raw_content = b"refresh_token=synthetic-secret"
            item.response.raw_content = b"access_token=synthetic-secret"
            addon.request(item)
            addon.responseheaders(item)
            addon.response(item)
            self.assertNotIn("events.jsonl", {path.name for path in root.iterdir()})
            self.assertNotIn("archive.jsonl", {path.name for path in root.iterdir()})

    def test_json_and_compressed_body_retain_wire_bytes(self) -> None:
        raw = gzip.compress(b'{"answer":42}')
        body = _body(raw, "application/json", "gzip")
        self.assertEqual(body["decoded"]["value"], {"answer": 42})
        self.assertEqual(body["wire"]["byte_length"], len(raw))

    def test_request_stream_and_archive_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            emitter = JsonlEmitter(root / "events.jsonl", "session-test")
            addon = LiveCapture(emitter, root / "archive.jsonl")
            item = flow()
            addon.request(item)
            addon.responseheaders(item)
            self.assertEqual([json.loads(line)["kind"] for line in (root / "events.jsonl").read_text().splitlines()], ["request.started", "response.started"])
            first = b'data: {"type":"message_start"}\n\n'
            second = b'data: {"type":"message_stop"}\n\n'
            self.assertEqual(item.response.stream(first), first)
            self.assertEqual(item.response.stream(second), second)
            addon.response(item)
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            for event in events:
                validate_event(event)
            self.assertEqual([event["kind"] for event in events], ["request.started", "response.started", "response.block", "response.block", "flow.completed"])
            self.assertEqual(events[0]["payload"]["request"]["headers"]["Authorization"], "[REDACTED]")
            self.assertEqual(events[1]["payload"]["headers"]["set-cookie"], "[REDACTED]")
            self.assertEqual(b"".join((first, second)), __import__("base64").b64decode(json.loads((root / "archive.jsonl").read_text())["response"]["body"]["wire"]["data"]))

    def test_error_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
            item = flow()
            addon.request(item)
            item.error = "connection reset"
            addon.error(item)
            event = json.loads((root / "events.jsonl").read_text().splitlines()[-1])
            validate_event(event)
            self.assertEqual(event["kind"], "flow.error")

    def test_codex_websocket_captures_logical_messages_without_handshake_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
            client = SimpleNamespace(
                content=b'{"type":"response.create","input":[{"type":"message"}]}',
                is_text=True, from_client=True, timestamp=1787164951.25,
            )
            server = SimpleNamespace(
                content=b'{"type":"response.completed"}',
                is_text=True, from_client=False, timestamp=1787164952.5,
            )
            item = flow("codex-ws")
            item.request.method = "GET"
            item.request.pretty_host = "chatgpt.com"
            item.request.pretty_url = "https://chatgpt.com/backend-api/codex/responses"
            item.request.headers = Headers({"Authorization": "synthetic-oauth-secret", "Cookie": "synthetic-cookie"})
            item.websocket = SimpleNamespace(messages=[client])
            addon.websocket_start(item)
            addon.websocket_message(item)
            item.websocket.messages.append(server)
            addon.websocket_message(item)
            addon.websocket_end(item)

            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            for event in events:
                validate_event(event)
            self.assertEqual([event["kind"] for event in events], ["websocket.message", "websocket.message", "websocket.closed"])
            self.assertTrue(all(event["protocol_version"] == "1.1" for event in events))
            self.assertEqual([event["payload"]["direction"] for event in events[:-1]], ["client_to_server", "server_to_client"])
            self.assertEqual([event["payload"]["message_index"] for event in events[:-1]], [0, 1])
            self.assertNotIn("synthetic-oauth-secret", (root / "events.jsonl").read_text())
            self.assertNotIn("synthetic-cookie", (root / "events.jsonl").read_text())
            archive = (root / "archive.jsonl").read_text()
            self.assertNotIn("synthetic-oauth-secret", archive)
            self.assertNotIn("synthetic-cookie", archive)
            self.assertEqual(len(archive.splitlines()), 3)
            self.assertEqual(events[-1]["payload"]["archive_status"], "written")

    def test_codex_websocket_rejects_other_paths_and_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
            for url in (
                "https://chatgpt.com/auth/token",
                "https://chatgpt.com/backend-api/codex/responses?access_token=synthetic",
                "https://api.openai.com/v1/responses",
            ):
                item = flow("codex-ws")
                item.request.method = "GET"
                item.request.pretty_host = url.split("/", 3)[2].split(":")[0]
                item.request.pretty_url = url
                item.websocket = SimpleNamespace(messages=[SimpleNamespace(
                    content=b"synthetic-secret", is_text=True, from_client=True, timestamp=1.0,
                )])
                addon.websocket_start(item)
                addon.websocket_message(item)
            self.assertFalse((root / "events.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
