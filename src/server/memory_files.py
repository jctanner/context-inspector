"""Read-only allowlisted files from the project-local container home mirror."""
from __future__ import annotations

import os
from pathlib import Path
import stat

MAX_BYTES = 1024 * 1024
MAX_FILES = 500
MAX_ENTRIES = 5000
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class MemoryError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def components(path: str) -> list[str]:
    parts = path.split("/")
    if len(path) > 2048 or any(not p or p in (".", "..") or "\\" in p or "\x00" in p for p in parts):
        raise MemoryError("Invalid memory path")
    if path != "CLAUDE.md" and not (len(parts) >= 4 and parts[0] == "projects" and parts[2] == "memory"
                                    and parts[-1].endswith(".md") and all(not p.startswith(".") for p in parts)):
        raise MemoryError("Path is outside supported memory locations")
    return parts


def open_directory(parent: int, name: str) -> int:
    return os.open(name, DIR_FLAGS, dir_fd=parent)


def root_fd(home: Path) -> int:
    if not home.is_absolute() or ".." in home.parts:
        raise MemoryError("Memory root must be an absolute configured path")
    fd = os.open("/", DIR_FLAGS)
    try:
        for name in (*home.parts[1:], ".claude"):
            child = open_directory(fd, name)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def metadata(path: str, info: os.stat_result) -> dict:
    return {"path": path, "size": info.st_size, "modified_at": info.st_mtime}


def read_file(root: int, path: str) -> dict:
    parts = components(path)
    parent = os.dup(root)
    fd = None
    try:
        for name in parts[:-1]:
            child = open_directory(parent, name)
            os.close(parent)
            parent = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise MemoryError("Only regular memory files without hard links can be viewed")
        if info.st_size > MAX_BYTES:
            raise MemoryError("Memory file exceeds the 1 MiB viewing limit", 413)
        with os.fdopen(fd, "rb") as source:
            fd = None
            data = source.read(MAX_BYTES + 1)
            after = os.fstat(source.fileno())
        if len(data) > MAX_BYTES:
            raise MemoryError("Memory file exceeds the 1 MiB viewing limit", 413)
        if (info.st_mtime_ns, info.st_size) != (after.st_mtime_ns, after.st_size):
            raise MemoryError("Memory file changed while reading; refresh and retry", 409)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise MemoryError("Memory file is not UTF-8 text", 415) from None
        if "\x00" in text:
            raise MemoryError("Memory file is not plain text", 415)
        return {**metadata(path, info), "content": text}
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def list_files(root: int) -> dict:
    files = []
    visited = 0
    truncated = False

    def walk(fd: int, prefix: list[str], depth: int = 0):
        nonlocal visited, truncated
        with os.scandir(fd) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_ENTRIES or len(files) >= MAX_FILES:
                    truncated = True
                    return
                name = entry.name
                if name.startswith(".") or "\\" in name:
                    continue
                parts = [*prefix, name]
                try:
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                        try:
                            components("/".join(parts))
                        except MemoryError:
                            continue
                        files.append(metadata("/".join(parts), info))
                    elif stat.S_ISDIR(info.st_mode):
                        allowed = (not prefix and name == "projects") or prefix == ["projects"] or (len(prefix) == 2 and name == "memory") or (len(prefix) >= 3 and prefix[2] == "memory")
                        if not allowed:
                            continue
                        if depth >= 12:
                            truncated = True
                            continue
                        child = open_directory(fd, name)
                        try:
                            walk(child, parts, depth + 1)
                        finally:
                            os.close(child)
                except OSError:
                    continue  # Deleted/replaced while listing; never follow a link.
    walk(root, [])
    return {"files": sorted(files, key=lambda f: f["path"]), "truncated": truncated}


def inspect_memory(action: str, path: str = "", *, home: Path) -> dict:
    if action not in ("list", "read"):
        raise MemoryError("Unsupported operation")
    if action == "read":
        components(path)
    try:
        root = root_fd(home)
    except FileNotFoundError:
        if action == "list":
            return {"files": [], "truncated": False}
        raise MemoryError("Memory file not found", 404) from None
    try:
        return list_files(root) if action == "list" else read_file(root, path)
    finally:
        os.close(root)
