#!/usr/bin/env python3
"""Synthetic MCP tools over stdio; no sockets, commands, or model calls.

Claude owns this long-running subprocess. Only JSON-RPC is written to stdout;
configuration diagnostics go to stderr. A reader thread waits for stdin while
the main loop polls configuration and serializes all protocol output.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import stat
import sys
import threading
import time


DEFAULT_CONFIG = {"tool_count": 1, "description_words": 200,
                  "schema_properties": 20, "seed": 42}
DEFAULT_PATH = Path("/workspace/.context/mcp-dump/config.json")
PROTOCOL = "2025-06-18"
PAGE_SIZE = 100
WORDS = """amber anchor apple autumn bamboo beacon berry birch blossom breeze
brook candle canyon cedar cherry cloud clover cobalt coral cotton crystal daisy
delta desert diamond eagle earth echo ember falcon feather fern field flint
forest frost garden garnet ginger glacier globe granite grape grass grove harbor
harvest hazel heron honey island ivory jade jasmine jewel juniper lagoon lake
lantern laurel lavender leaf lemon linen lotus maple marble meadow melon mist
moss mountain nectar ocean olive opal orange orchid otter pebble pepper petal
pine planet plum pollen pond poplar prairie prism quartz quill rain raven reed
reef ribbon ripple river robin rose ruby saffron sage sand sapphire satin shell
silver sky slate snow solar sparrow spring spruce star stone storm stream summit
sunset teal thistle thunder timber topaz tulip valley velvet violet walnut water
wave wheat willow wind winter wood wren yellow zephyr""".split()


def validate_config(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_CONFIG):
        raise ValueError("config must contain exactly tool_count, description_words, schema_properties, seed")
    limits = {"tool_count": (0, 10000), "description_words": (0, 2000),
              "schema_properties": (0, 100), "seed": (0, 2**32 - 1)}
    for key, (lower, upper) in limits.items():
        if type(value[key]) is not int or not lower <= value[key] <= upper:
            raise ValueError(f"{key} must be an integer in {lower}..{upper}")
    # Bound aggregate generated metadata, independently of pagination.
    estimate = value["tool_count"] * (
        500 + value["description_words"] * 10 + value["schema_properties"] * 300)
    if estimate > 64_000_000:
        raise ValueError("combined tool metadata exceeds the 64 MB experiment limit")
    return dict(value)


def tool_definition(config, index):
    # Changing the count does not change surviving tools' descriptions/schemas.
    rng = random.Random(f'{config["seed"]}:{index}')
    words = lambda count: " ".join(rng.choices(WORDS, k=count))
    return {
        "name": f"dump_tool_{index:05d}",
        "description": "Synthetic no-op context experiment. " + words(config["description_words"]),
        "inputSchema": {
            "type": "object",
            "properties": {
                f"field_{number:03d}": {"type": "string", "description": words(16)}
                for number in range(1, config["schema_properties"] + 1)
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
    }


class ConfigState:
    def __init__(self, path):
        self.path = path
        self.config = {**DEFAULT_CONFIG, "tool_count": 0}
        self.last_error = None
        self.revision = ""

    def refresh(self):
        try:
            # Nonblocking open + regular-file check also avoids hanging on a FIFO.
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError("config must be a regular file")
                raw = handle.read(65537)
            if len(raw) > 65536:
                raise ValueError("config exceeds 64 KiB")
            config = validate_config(json.loads(raw))
        except (OSError, ValueError) as exc:
            # Never echo file contents or tool arguments into diagnostics.
            error = str(exc) if not isinstance(exc, json.JSONDecodeError) else "incomplete or invalid JSON"
            if error != self.last_error:
                print(f"mcp-dump: keeping previous tools: {error}", file=sys.stderr, flush=True)
                self.last_error = error
            return False
        self.last_error = None
        if config == self.config and self.revision:
            return False
        self.config = config
        self.revision = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
        print(f'mcp-dump: advertising {config["tool_count"]} tools ({self.revision})',
              file=sys.stderr, flush=True)
        return True


class ProtocolError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Server:
    def __init__(self, state):
        self.state = state
        self.initialized = False
        self.negotiated = False

    def dispatch(self, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return self.error(None, -32600, "Invalid Request")
        method = message["method"]
        if "id" not in message:
            if method == "notifications/initialized" and self.negotiated:
                self.initialized = True
            return None
        request_id = message["id"]
        if type(request_id) not in (str, int):
            return self.error(None, -32600, "Invalid request ID")
        try:
            params = message.get("params", {})
            if not isinstance(params, dict):
                raise ProtocolError(-32602, "params must be an object")
            if method == "initialize":
                if not isinstance(params.get("protocolVersion"), str):
                    raise ProtocolError(-32602, "protocolVersion is required")
                self.negotiated = True
                result = {"protocolVersion": PROTOCOL,
                          "capabilities": {"tools": {"listChanged": True}},
                          "serverInfo": {"name": "context-inspector-mcp-dump", "version": "1.0.0"}}
            elif method == "ping":
                result = {}
            elif not self.initialized:
                raise ProtocolError(-32000, "Session is not initialized")
            elif method == "tools/list":
                result = self.list_tools(params)
            elif method == "tools/call":
                result = self.call_tool(params)
            else:
                raise ProtocolError(-32601, "Method not found")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ProtocolError as exc:
            return self.error(request_id, exc.code, exc.message)

    @staticmethod
    def error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def list_tools(self, params):
        offset = 0
        if "cursor" in params:
            cursor = params["cursor"]
            if not isinstance(cursor, str) or not re.fullmatch(r"[a-f0-9]{16}:[0-9]{1,5}", cursor):
                raise ProtocolError(-32602, "Invalid cursor")
            revision, number = cursor.split(":")
            offset = int(number)
            if revision != self.state.revision or not 0 < offset < self.state.config["tool_count"]:
                raise ProtocolError(-32602, "Stale cursor; restart tools/list without a cursor")
        config = self.state.config
        end = min(offset + PAGE_SIZE, config["tool_count"])
        result = {"tools": [tool_definition(config, index) for index in range(offset + 1, end + 1)]}
        if end < config["tool_count"]:
            result["nextCursor"] = f"{self.state.revision}:{end}"
        return result

    def call_tool(self, params):
        name = params.get("name")
        match = re.fullmatch(r"dump_tool_([0-9]{5})", name) if isinstance(name, str) else None
        if not match or not 1 <= int(match[1]) <= self.state.config["tool_count"]:
            raise ProtocolError(-32602, "Unknown tool")
        arguments = params.get("arguments", {})
        allowed = {f"field_{index:03d}" for index in range(1, self.state.config["schema_properties"] + 1)}
        if not isinstance(arguments, dict) or any(key not in allowed or not isinstance(value, str)
                                                  for key, value in arguments.items()):
            return {"content": [{"type": "text", "text": "Invalid dummy-tool arguments."}], "isError": True}
        return {"content": [{"type": "text", "text": f"{name}: synthetic success; no action performed."}],
                "isError": False}


def emit(message):
    print(json.dumps(message, separators=(",", ":")), flush=True)


def serve(path, interval):
    state = ConfigState(path)
    state.refresh()
    server = Server(state)
    incoming = queue.Queue(maxsize=32)

    def read_input():
        for line in sys.stdin:
            incoming.put(line)
        incoming.put(None)

    threading.Thread(target=read_input, daemon=True).start()
    next_poll = time.monotonic() + interval
    while True:
        if time.monotonic() >= next_poll:
            if state.refresh() and server.initialized:
                emit({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
            next_poll = time.monotonic() + interval
        try:
            line = incoming.get(timeout=max(0, next_poll - time.monotonic()))
        except queue.Empty:
            continue
        if line is None:
            return
        try:
            message = json.loads(line)
        except ValueError:
            emit(server.error(None, -32700, "Parse error"))
            continue
        response = server.dispatch(message)
        if response is not None:
            emit(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()
    if not math.isfinite(args.poll_interval) or args.poll_interval < 0.05:
        parser.error("poll interval must be finite and at least 0.05 seconds")
    # Only create absent configuration; preserve user edits across stack restarts.
    args.config.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.config.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
    except FileExistsError:
        pass
    try:
        serve(args.config, args.poll_interval)
    except (BrokenPipeError, KeyboardInterrupt):
        # The client owns our lifetime. Avoid stdout-flush errors at shutdown.
        os._exit(0)


if __name__ == "__main__":
    main()
