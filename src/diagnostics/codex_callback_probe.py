"""Opt-in native Codex external-auth test with synthetic tokens and local model.

No host credentials/config are read. No requests go to a real model service.
This is compatibility evidence, not the production credential bridge.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from .codex_refresh_probe import Authority, Client, jwt


class CallbackAuthority(Authority):
    def __init__(self):
        super().__init__()
        self.old_access = None
        self.model_attempts = []

    def handler(self):
        parent = super().handler()
        authority = self

        class Handler(parent):
            def do_POST(self):
                if self.path != "/v1/responses":
                    return super().do_POST()
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                old = self.headers.get("Authorization") == "Bearer " + authority.old_access
                authority.model_attempts.append({"old_token": old})
                if old:
                    body = b'{"error":{"message":"synthetic unauthorized","type":"invalid_request_error"}}'
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                else:
                    item = {"type": "message", "id": "msg-synthetic", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": "synthetic response", "annotations": []}]}
                    values = [
                        {"type": "response.created", "response": {"id": "resp-synthetic", "status": "in_progress", "output": []}},
                        {"type": "response.output_item.done", "output_index": 0, "item": item},
                        {"type": "response.completed", "response": {"id": "resp-synthetic", "status": "completed", "output": [item],
                         "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}},
                    ]
                    body = "".join("data: " + json.dumps(value) + "\n\n" for value in values).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        return Handler


def probe(container_image: str | None = None):
    authority = CallbackAuthority()
    server = ThreadingHTTPServer(("127.0.0.1", 0), authority.handler())
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    clients = []
    native_server = None
    try:
        with tempfile.TemporaryDirectory(prefix="ci-codex-callback-") as directory:
            root = Path(directory)
            host, inspector = root / "host", root / "inspector"
            host.mkdir(mode=0o700)
            inspector.mkdir(mode=0o700)
            path = host / "auth.json"
            path.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {
                "id_token": jwt(), "access_token": jwt(), "refresh_token": "synthetic-refresh-0", "account_id": "synthetic-account"},
                "last_refresh": datetime.now(timezone.utc).isoformat()}))
            path.chmod(0o600)
            url = f"http://127.0.0.1:{server.server_port}"
            socket_path = root / "host.sock"
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CODEX_HOME": str(host),
                   "CODEX_REFRESH_TOKEN_URL_OVERRIDE": url + "/token", "CODEX_AUTHAPI_BASE_URL": url,
                   "HTTP_PROXY": url, "HTTPS_PROXY": url, "ALL_PROXY": url, "NO_PROXY": "127.0.0.1,localhost"}
            native_server = subprocess.Popen([
                "codex", "app-server", "--listen", "unix://" + str(socket_path),
                "-c", 'cli_auth_credentials_store="file"', "-c", f'chatgpt_base_url="{url}/backend-api/"',
                "-c", "analytics.enabled=false"], cwd=host, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 10
            while not socket_path.exists():
                if native_server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Synthetic native server failed to create its socket")
                time.sleep(0.05)
            # Both WebSocket clients attach to the same already-running manager.
            clients.append(Client(host, url, socket_path=socket_path))
            clients.append(Client(host, url, socket_path=socket_path))
            with ThreadPoolExecutor(2) as pool:
                refreshed = list(pool.map(lambda client: client.rpc(2, "getAuthStatus", {"includeToken": True, "refreshToken": True}), clients))
            if any("result" not in result for result in refreshed):
                raise RuntimeError("Synthetic shared-server refresh failed")
            shared_count = len(authority.refreshes)
            shared_unique = len(set(authority.refreshes)) == shared_count
            current = clients[0].rpc(3, "getAuthStatus", {"includeToken": True, "refreshToken": False})
            authority.old_access = current["result"]["authToken"]
            clients.append(Client(inspector, url, container_image, share_auth=False, config={
                "model_provider": '"probe"', "model": '"synthetic-model"',
                "model_providers.probe": '{name="Synthetic local endpoint",base_url="' + url + '/v1",wire_api="responses",requires_openai_auth=true,supports_websockets=false}',
            }))
            external = clients[-1]
            login = external.rpc(2, "account/login/start", {"type": "chatgptAuthTokens", "accessToken": authority.old_access,
                "chatgptAccountId": "synthetic-account", "chatgptPlanType": "plus"})
            if "result" not in login:
                raise RuntimeError("Synthetic external login failed")
            thread = external.rpc(3, "thread/start", {"model": "synthetic-model", "cwd": "/codex-home" if container_image else str(inspector), "ephemeral": True,
                "approvalPolicy": "never", "sandbox": "read-only"})
            if "result" not in thread:
                raise RuntimeError("Synthetic thread startup failed")
            external.send({"id": 4, "method": "turn/start", "params": {"threadId": thread["result"]["thread"]["id"],
                "input": [{"type": "text", "text": "Return a synthetic response.", "text_elements": []}]}})
            callbacks = 0
            turn_status = None
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    message = external.messages.get(timeout=1)
                except queue.Empty:
                    continue
                if message is None:
                    raise RuntimeError("Synthetic inspector connection closed")
                if message.get("method") == "account/chatgptAuthTokens/refresh":
                    params = message.get("params", {})
                    if params.get("previousAccountId") != "synthetic-account" or params.get("reason") != "unauthorized":
                        raise RuntimeError("Unexpected synthetic refresh callback")
                    refreshed = clients[0].rpc(10 + callbacks, "getAuthStatus", {"includeToken": True, "refreshToken": True})
                    token = refreshed.get("result", {}).get("authToken")
                    if not token:
                        raise RuntimeError("Synthetic host did not supply a replacement token")
                    external.send({"id": message["id"], "result": {"accessToken": token,
                        "chatgptAccountId": "synthetic-account", "chatgptPlanType": "plus"}})
                    callbacks += 1
                if message.get("method") == "turn/completed":
                    turn_status = message.get("params", {}).get("turn", {}).get("status")
                    break
            return {"synthetic_only": True, "native_socket_attachment": True,
                    "container_image": container_image,
                    "shared_manager_refresh_requests": shared_count, "shared_manager_used_distinct_refresh_tokens": shared_unique,
                    "refresh_callbacks": callbacks, "model_attempts": authority.model_attempts, "turn_status": turn_status,
                    "inspector_auth_file_created": (inspector / ("container-home/auth.json" if container_image else "auth.json")).exists(),
                    "limitations": ["no real host daemon attachment", "no container TUI", "no real model or proxy capture"]}
    finally:
        for client in clients:
            client.close()
        if native_server is not None:
            native_server.terminate()
            try:
                native_server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                native_server.kill()
                native_server.wait()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container-image", help="Existing image for isolated external-auth app server; no credential file mount")
    print(json.dumps(probe(parser.parse_args().container_image), indent=2))
