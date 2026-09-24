"""Opt-in native Codex refresh probe, using only synthetic tokens and localhost.

Run: .venv/bin/python -m src.diagnostics.codex_refresh_probe
No real auth/config files are read. No model requests are made. The fake token
endpoint deliberately rejects reuse; this tests client coordination, not the
real provider's undocumented rotation/grace policy.
"""
from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid
from urllib.parse import parse_qs


def jwt() -> str:
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return ".".join((encode({"alg": "none"}), encode({"email": "synthetic@example.invalid", "jti": uuid.uuid4().hex, "exp": int(time.time()) + 3600,
        "https://api.openai.com/auth": {"chatgpt_account_id": "synthetic-account", "chatgpt_plan_type": "plus", "chatgpt_user_id": "synthetic-user"}}), "synthetic"))


class Authority:
    def __init__(self):
        self.lock = threading.Lock()
        self.refreshes = []
        self.used = set()
        self.requests = []
        self.barrier = None

    def handler(self):
        authority = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_CONNECT(self):
                authority.requests.append(["CONNECT", self.path])
                self.send_error(403)
            def do_GET(self):
                authority.requests.append(["GET", self.path])
                if self.path == "/backend-api/wham/accounts/check":
                    value = {"accounts": [{"id": "synthetic-account", "workspace_backend_origin": "https://chatgpt.com", "account_routing_override": "NO_CONSTRAINT"}], "default_account_id": "synthetic-account"}
                elif self.path == "/backend-api/wham/config/bundle":
                    value = {}
                else:
                    self.send_error(404)
                    return
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def do_POST(self):
                authority.requests.append(["POST", self.path])
                if self.path != "/token":
                    self.send_error(404)
                    return
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if "application/json" in self.headers.get("Content-Type", ""):
                    token = json.loads(raw).get("refresh_token")
                else:
                    token = parse_qs(raw.decode()).get("refresh_token", [None])[0]
                if not isinstance(token, str) or not token.startswith("synthetic-refresh-"):
                    self.send_error(400)
                    return
                with authority.lock:
                    authority.refreshes.append(token)
                    reused = token in authority.used
                    authority.used.add(token)
                    next_token = f"synthetic-refresh-{len(authority.used)}"
                if authority.barrier:
                    try:
                        authority.barrier.wait(timeout=5)
                    except threading.BrokenBarrierError:
                        pass
                value = ({"error": {"code": "refresh_token_reused", "message": "synthetic rotation race"}}
                         if reused else {"access_token": jwt(), "refresh_token": next_token, "id_token": jwt()})
                data = json.dumps(value).encode()
                self.send_response(401 if reused else 200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        return Handler


class Client:
    def __init__(self, root: Path, url: str, container_image: str | None = None, *, socket_path: Path | None = None, config: dict | None = None, share_auth: bool = True):
        # These are Codex's documented configuration variables, scoped to the
        # child only; no host environment/configuration is forwarded.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CODEX_HOME": str(root),
               "CODEX_REFRESH_TOKEN_URL_OVERRIDE": url + "/token", "CODEX_AUTHAPI_BASE_URL": url, "HTTP_PROXY": url,
               "HTTPS_PROXY": url, "ALL_PROXY": url, "NO_PROXY": "127.0.0.1,localhost"}
        args = ["app-server", "--stdio", "-c", 'cli_auth_credentials_store="file"',
                "-c", f'chatgpt_base_url="{url}/backend-api/"', "-c", "analytics.enabled=false"]
        for key, value in (config or {}).items():
            args += ["-c", f"{key}={value}"]
        if socket_path is not None:
            if container_image or config:
                raise ValueError("Socket attachment must not override the running server")
        command = ["codex", *args]
        self.container_name = None
        process_env = env
        if container_image:
            binary = Path("/usr/local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex")
            if not binary.is_file():
                raise RuntimeError("Expected installed Codex Linux binary is unavailable")
            container_home = root / "container-home"
            container_home.mkdir()
            self.container_name = "context-inspector-auth-probe-" + uuid.uuid4().hex[:12]
            command = ["podman", "run", "--rm", "--interactive", "--pull=never", "--name", self.container_name,
                       "--network=host", "--userns=keep-id:uid=1000,gid=1000", "--user=1000:1000",
                       "--security-opt=label=disable", "--workdir=/codex-home",
                       "--volume", f"{binary}:/codex:ro", "--volume", f"{container_home}:/codex-home:rw"]
            if share_auth:
                command += ["--volume", f"{root / 'auth.json'}:/codex-home/auth.json:rw"]
            for key, value in {**env, "CODEX_HOME": "/codex-home"}.items():
                if key != "PATH":
                    command += ["--env", f"{key}={value}"]
            command += ["--entrypoint=/codex", container_image, *args]
            process_env = None  # Podman's host runtime env is not passed into the container.
        self.socket = None
        if socket_path is not None:
            from websockets.sync.client import unix_connect
            self.socket = unix_connect(str(socket_path), uri="ws://localhost/", open_timeout=5)
        else:
            self.process = subprocess.Popen(command, cwd=root, env=process_env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, start_new_session=True)
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.rpc(1, "initialize", {"clientInfo": {"name": "synthetic-refresh-probe", "version": "1"},
                                       "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        from websockets.exceptions import ConnectionClosed
        try:
            for line in self.socket if self.socket is not None else self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    pass
        except ConnectionClosed:
            pass
        finally:
            self.messages.put(None)

    def send(self, message):
        if self.socket is not None:
            self.socket.send(json.dumps(message))
            return
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def rpc(self, ident, method, params):
        self.send({"id": ident, "method": method, "params": params})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            message = self.messages.get(timeout=max(0.1, deadline - time.monotonic()))
            if message is None:
                raise RuntimeError("Synthetic native connection closed")
            if message.get("id") == ident:
                return message
        raise TimeoutError(method)

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.reader.join(timeout=2)
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if self.container_name:
            subprocess.run(["podman", "rm", "--force", self.container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()


def probe(concurrent: bool, container_image: str | None = None):
    authority = Authority()
    server = ThreadingHTTPServer(("127.0.0.1", 0), authority.handler())
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    clients = []
    try:
        with tempfile.TemporaryDirectory(prefix="context-inspector-synthetic-auth-") as directory:
            root = Path(directory)
            auth = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None, "tokens": {"id_token": jwt(),
                    "access_token": "synthetic-access-0", "refresh_token": "synthetic-refresh-0", "account_id": "synthetic-account"},
                    "last_refresh": datetime.now(timezone.utc).isoformat()}
            path = root / "auth.json"
            path.write_text(json.dumps(auth)); path.chmod(0o600)
            url = f"http://127.0.0.1:{server.server_port}"
            clients.append(Client(root, url))
            clients.append(Client(root, url, container_image))
            # Both native managers cache the same initial credentials.
            initial = [client.rpc(2, "account/read", {"refreshToken": False}) for client in clients]
            if any(item.get("result", {}).get("account", {}).get("type") != "chatgpt" for item in initial):
                return {"scenario": "concurrent" if concurrent else "sequential", "error": "synthetic login did not load", "initial": initial, "local_requests": authority.requests}
            if concurrent:
                authority.barrier = threading.Barrier(2)
                with ThreadPoolExecutor(2) as pool:
                    results = list(pool.map(lambda client: client.rpc(3, "account/read", {"refreshToken": True}), clients))
            else:
                results = [client.rpc(3, "account/read", {"refreshToken": True}) for client in clients]
            tokens = authority.refreshes
            return {"scenario": "concurrent" if concurrent else "sequential", "refresh_requests": len(tokens),
                    "same_refresh_token_submitted_twice": len(tokens) != len(set(tokens)),
                    "client_errors": [item.get("error", {}).get("message") for item in results],
                    "auth_file_parseable": isinstance(json.loads(path.read_text()), dict)}
    finally:
        for client in clients:
            client.close()
        server.shutdown(); server.server_close(); worker.join(timeout=2)


def probe_external_auth():
    """Test native access-token handoff, without claiming daemon/refresh support."""
    authority = Authority()
    server = ThreadingHTTPServer(("127.0.0.1", 0), authority.handler())
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    clients = []
    try:
        with tempfile.TemporaryDirectory(prefix="context-inspector-external-auth-") as directory:
            host = Path(directory) / "host"
            inspector = Path(directory) / "inspector"
            host.mkdir(mode=0o700)
            inspector.mkdir(mode=0o700)
            path = host / "auth.json"
            path.write_text(json.dumps({
                "auth_mode": "chatgpt", "tokens": {"id_token": jwt(), "access_token": jwt(),
                "refresh_token": "synthetic-refresh-0", "account_id": "synthetic-account"},
                "last_refresh": datetime.now(timezone.utc).isoformat(),
            }))
            path.chmod(0o600)
            original = path.read_bytes()
            url = f"http://127.0.0.1:{server.server_port}"
            clients.append(Client(host, url))
            clients.append(Client(inspector, url))
            exported = clients[0].rpc(2, "getAuthStatus", {"includeToken": True, "refreshToken": False})
            token = exported.get("result", {}).get("authToken")
            if not isinstance(token, str) or not token:
                return {"stage": "export", "success": False}
            login = clients[1].rpc(2, "account/login/start", {
                "type": "chatgptAuthTokens", "accessToken": token,
                "chatgptAccountId": "synthetic-account", "chatgptPlanType": "plus",
            })
            account = clients[1].rpc(3, "account/read", {"refreshToken": False})
            # Never print RPC errors or token-bearing results, even in this probe.
            return {"stage": "external_login", "login_succeeded": "result" in login,
                    "chatgpt_account_loaded": account.get("result", {}).get("account", {}).get("type") == "chatgpt",
                    "inspector_auth_file_created": (inspector / "auth.json").exists(),
                    "host_auth_unchanged": path.read_bytes() == original,
                    "refresh_requests": len(authority.refreshes),
                    "limitations": ["standalone synthetic app servers", "no daemon attachment", "no unauthorized refresh callback", "no model request"]}
    finally:
        for client in clients:
            client.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container-image", help="Run the second client in an existing image; only synthetic auth.json is shared")
    parser.add_argument("--external-auth", action="store_true", help="Probe synthetic native access-token handoff instead of shared-file refresh")
    options = parser.parse_args()
    print(json.dumps({"synthetic_only": True, "version": subprocess.check_output(["codex", "--version"], text=True).strip(),
                      "container_image": options.container_image, "results": [probe_external_auth()] if options.external_auth else [probe(False, options.container_image), probe(True, options.container_image)]}, indent=2))
