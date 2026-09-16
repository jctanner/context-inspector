from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from src.runtime.mcp_dump.server import DEFAULT_CONFIG, tool_definition, validate_config


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "src/runtime/mcp_dump/server.py"


class Client:
    def __init__(self, process):
        self.process = process
        self.messages = queue.Queue()
        self.notifications = []
        self.sequence = 0
        def read():
            for line in process.stdout:
                self.messages.put(json.loads(line))
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, message):
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.sequence += 1
        self.send({"id": self.sequence, "method": method, "params": params or {}})
        deadline = time.monotonic() + 10
        while True:
            message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if "id" not in message:
                self.notifications.append(message)
                continue
            assert message["id"] == self.sequence, message
            return message

    def changed(self):
        message = self.notifications.pop(0) if self.notifications else self.messages.get(timeout=10)
        assert message == {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}, message

    def initialize(self):
        result = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "fixture", "version": "1"}})["result"]
        assert result["capabilities"]["tools"]["listChanged"] is True
        self.send({"method": "notifications/initialized"})
        self.request("ping")  # Fence initialized before edits.


@contextmanager
def running(directory, container=False):
    config = Path(directory) / "config.json"
    command = [sys.executable, str(SCRIPT), "--config", str(config), "--poll-interval", "0.05"]
    if container:
        command = ["podman", "run", "--rm", "-i", "--network", "none",
                   "--userns=keep-id:uid=1000,gid=1000", "--user", "1000:1000",
                   "--volume", f"{SCRIPT}:/fixture/server.py:ro,z",
                   "--volume", f"{directory}:/config:rw,z", "--entrypoint", "python3",
                   "localhost/claude-task-runner:latest", "/fixture/server.py",
                   "--config", "/config/config.json", "--poll-interval", "0.05"]
    with tempfile.TemporaryFile(mode="w+") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, text=True, encoding="utf-8")
        client = Client(process)
        try:
            yield client, config
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
            client.reader.join(timeout=2)
            process.stdout.close()
            errors.seek(0)
            assert process.returncode == 0, errors.read()


def write_config(path, **changes):
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps({**DEFAULT_CONFIG, **changes}))
    temporary.replace(path)


class MCPDumpTests(unittest.TestCase):
    def exercise_dynamic(self, container=False):
        with tempfile.TemporaryDirectory() as directory, running(directory, container) as (client, config):
            client.initialize()
            initial = client.request("tools/list")["result"]["tools"]
            self.assertEqual(len(initial), 1)
            self.assertEqual(json.loads(config.read_text()), DEFAULT_CONFIG)
            write_config(config, tool_count=1000)
            client.changed()
            listing = client.request("tools/list")["result"]
            stale_cursor = listing["nextCursor"]
            tools = list(listing["tools"])
            while "nextCursor" in listing:
                listing = client.request("tools/list", {"cursor": listing["nextCursor"]})["result"]
                tools.extend(listing["tools"])
            self.assertEqual(len(tools), 1000)
            self.assertEqual(len({tool["name"] for tool in tools}), 1000)
            self.assertEqual(tools[0], initial[0])
            self.assertEqual(len(tools[-1]["inputSchema"]["properties"]), 20)
            result = client.request("tools/call", {"name": "dump_tool_01000", "arguments": {"field_001": "secret"}})["result"]
            self.assertFalse(result["isError"])
            self.assertNotIn("secret", json.dumps(result))
            config.write_text('{"tool_count":')
            time.sleep(0.2)
            self.assertEqual(len(client.request("tools/list")["result"]["tools"]), 100)
            self.assertEqual(client.notifications, [])
            config.unlink()
            time.sleep(0.2)
            self.assertEqual(len(client.request("tools/list")["result"]["tools"]), 100)
            write_config(config, tool_count=2)
            client.changed()
            self.assertEqual(len(client.request("tools/list")["result"]["tools"]), 2)
            self.assertIn("error", client.request("tools/list", {"cursor": stale_cursor}))
            self.assertIn("error", client.request("tools/call", {"name": "dump_tool_01000"}))
            write_config(config, tool_count=0)
            client.changed()
            self.assertEqual(client.request("tools/list")["result"], {"tools": []})
            write_config(config, tool_count=1, seed=43, description_words=10, schema_properties=2)
            client.changed()
            changed = client.request("tools/list")["result"]["tools"][0]
            self.assertNotEqual(changed["description"], initial[0]["description"])
            self.assertEqual(len(changed["inputSchema"]["properties"]), 2)
            self.assertIsNone(client.process.poll())

    def test_dynamic_stdio(self):
        self.exercise_dynamic()

    @unittest.skipUnless(os.environ.get("CONTEXT_INSPECTOR_TEST_MCP") == "1", "opt-in real agent image")
    def test_dynamic_stdio_in_agent_container(self):
        self.exercise_dynamic(container=True)

    def test_initial_invalid_and_semantically_unchanged_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{")
            with running(directory) as (client, config):
                client.initialize()
                self.assertEqual(client.request("tools/list")["result"], {"tools": []})
                self.assertEqual(config.read_text(), "{")
                write_config(config)
                client.changed()
                config.write_text(json.dumps(DEFAULT_CONFIG, indent=4))
                time.sleep(0.2)
                self.assertEqual(len(client.request("tools/list")["result"]["tools"]), 1)
                self.assertEqual(client.notifications, [])

    def test_validation_and_determinism(self):
        for changes in ({"tool_count": -1}, {"tool_count": True}, {"seed": "42"},
                        {"schema_properties": 101}, {"description_words": 2001},
                        {"extra": 1}):
            with self.assertRaises(ValueError):
                validate_config({**DEFAULT_CONFIG, **changes})
        self.assertEqual(tool_definition(DEFAULT_CONFIG, 1), tool_definition(DEFAULT_CONFIG, 1))
        self.assertNotEqual(tool_definition(DEFAULT_CONFIG, 1), tool_definition(DEFAULT_CONFIG, 2))

    def test_large_count_names_and_cursors(self):
        from src.runtime.mcp_dump.server import ConfigState, Server
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_config(path, tool_count=200000)
            state = ConfigState(path)
            self.assertTrue(state.refresh())
            server = Server(state)
            page = server.list_tools({"cursor": f"{state.revision}:100000"})
            self.assertEqual(page["tools"][0]["name"], "dump_tool_100001")
            self.assertFalse(server.call_tool({"name": "dump_tool_100001"})["isError"])
            self.assertEqual(validate_config({**DEFAULT_CONFIG, "tool_count": 100000})["tool_count"], 100000)

    def test_protocol_errors(self):
        with tempfile.TemporaryDirectory() as directory, running(directory) as (client, config):
            self.assertIn("error", client.request("tools/list"))
            client.initialize()
            self.assertEqual(client.request("unknown")["error"]["code"], -32601)
            self.assertIn("error", client.request("tools/list", {"cursor": "bad"}))
            self.assertIn("error", client.request("tools/call", {"name": "bad"}))
            result = client.request("tools/call", {"name": "dump_tool_00001", "arguments": {"field_001": 2}})
            self.assertTrue(result["result"]["isError"])
            client.process.stdin.write("not json\n")
            client.process.stdin.flush()
            self.assertEqual(client.messages.get(timeout=2)["error"]["code"], -32700)
            self.assertEqual(client.request("ping")["result"], {})

    def test_runtime_wiring(self):
        script = ROOT / "src/runtime/mcp-dump-env.sh"
        command = 'runtime_dir=$1; agent_command=$2; mounts=(); source "$1/mcp-dump-env.sh"; configure_mcp_dump; printf "%s\\0" "${mounts[@]}" "${mcp_dump_args[@]}"'
        for enabled, agent in (("1", "claude"), ("0", "claude"), ("1", "bash")):
            result = subprocess.run(["bash", "-c", command, "fixture", str(script.parent), agent],
                                    env={**os.environ, "CONTEXT_INSPECTOR_MCP_DUMP_ENABLED": enabled},
                                    capture_output=True, check=True)
            args = result.stdout.decode().split("\0")
            self.assertEqual("--mcp-config" in args, enabled == "1" and agent == "claude")
            self.assertNotIn("--strict-mcp-config", args)
        config = json.loads((script.parent / "mcp_dump/claude.json").read_text())
        server = config["mcpServers"]["mcp-dump"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "python3")
        self.assertIn("/workspace/.context/mcp-dump/config.json", server["args"])
        runner = (script.parent / "run.sh").read_text()
        self.assertIn('"${tracing_args[@]}" "${mcp_dump_args[@]}" "$@"', runner)


if __name__ == "__main__":
    unittest.main()
