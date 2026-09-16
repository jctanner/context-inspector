"""Fixed-path MCP count edits; never accept a browser-supplied filesystem path."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import uuid

from fastapi import HTTPException
from src.runtime.mcp_dump.server import DEFAULT_CONFIG


LOCK = threading.Lock()


@contextmanager
def directory(workspace: Path, create=False):
    descriptors = []
    try:
        fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in (".context", "mcp-dump"):
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        yield fd
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def read_at(fd):
    try:
        descriptor = os.open("config.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return dict(DEFAULT_CONFIG), b""
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise HTTPException(400, "MCP config must be a regular file without hard links")
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise HTTPException(400, "MCP config file is too large to edit")
    try:
        config = json.loads(raw)
    except ValueError:
        raise HTTPException(409, "MCP config contains invalid JSON; repair the file first") from None
    if not isinstance(config, dict):
        raise HTTPException(409, "MCP config must be a JSON object")
    return config, raw


def snapshot(config, raw):
    count = config.get("tool_count")
    return {"tool_count": str(count) if type(count) is int else None,
            "revision": hashlib.sha256(raw).hexdigest()}


def get_count(workspace):
    try:
        with LOCK, directory(workspace) as fd:
            return snapshot(*read_at(fd))
    except FileNotFoundError:
        return snapshot(DEFAULT_CONFIG, b"")
    except OSError:
        raise HTTPException(400, "MCP config is unavailable or has an unsafe path") from None


def set_count(workspace, count, revision):
    if type(count) is not int or count <= 0:
        raise HTTPException(422, "Enter a positive integer")
    try:
        with LOCK, directory(workspace, create=True) as fd:
            config, previous = read_at(fd)
            if hashlib.sha256(previous).hexdigest() != revision:
                raise HTTPException(409, "Config changed elsewhere. Refresh and try again.")
            config["tool_count"] = count
            raw = (json.dumps(config, indent=2) + "\n").encode()
            temporary = f".config-{uuid.uuid4().hex}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=fd)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                if read_at(fd)[1] != previous:
                    raise HTTPException(409, "Config changed elsewhere. Refresh and try again.")
                os.replace(temporary, "config.json", src_dir_fd=fd, dst_dir_fd=fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError:
                    pass
            return snapshot(config, raw)
    except OSError:
        raise HTTPException(400, "Could not save MCP config; check file access") from None
