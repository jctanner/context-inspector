"""Bounded read-only browsing of a server-selected local directory root."""

from contextlib import contextmanager
import heapq
import os
from pathlib import Path
import stat

from fastapi import HTTPException


MAX_BYTES = 1024 * 1024
FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def parts(path):
    if path == "":
        return []
    result = path.split("/")
    if len(path) > 2048 or any(not item or item in (".", "..") or "\\" in item or "\x00" in item for item in result):
        raise HTTPException(400, "Invalid root-relative path")
    return result


@contextmanager
def directory(root: Path, components):
    if not root.is_absolute() or ".." in root.parts:
        raise HTTPException(400, "Browser root must be an absolute configured path")
    fd = os.open("/", FLAGS)
    try:
        for name in [*root.parts[1:], *components]:
            child = os.open(name, FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def listing(fd, path, after, limit):
    def entries():
        with os.scandir(fd) as scan:
            for item in scan:
                try:
                    info = item.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                kind = ("directory" if stat.S_ISDIR(info.st_mode) else "symlink" if stat.S_ISLNK(info.st_mode)
                        else "file" if stat.S_ISREG(info.st_mode) else "special")
                key = ("0:" if kind == "directory" else "1:") + item.name
                if key <= after:
                    continue
                relative = f"{path}/{item.name}" if path else item.name
                accessible = kind in ("directory", "file") and (kind == "directory" or info.st_nlink == 1)
                try:
                    parts(relative)
                    relative.encode("utf-8")
                except (HTTPException, UnicodeError):
                    accessible = False
                yield key, {"name": item.name, "path": relative, "kind": kind,
                            "size": info.st_size, "modified_at": info.st_mtime, "accessible": accessible}
    page = heapq.nsmallest(limit + 1, entries(), key=lambda item: item[0])
    return {"path": path, "entries": [entry for _, entry in page[:limit]],
            "next_cursor": page[limit - 1][0] if len(page) > limit else None}


def read(fd, name, path):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise HTTPException(400, "Only regular files without hard links can be previewed")
        if info.st_size > MAX_BYTES:
            raise HTTPException(413, "File exceeds the 1 MiB preview limit")
        data = source.read(MAX_BYTES + 1)
        after = os.fstat(source.fileno())
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File exceeds the 1 MiB preview limit")
    if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise HTTPException(409, "File changed while reading; refresh and retry")
    try:
        content = data.decode("utf-8")
    except UnicodeError:
        raise HTTPException(415, "Binary or non-UTF-8 file; preview unavailable") from None
    if "\x00" in content:
        raise HTTPException(415, "Binary file; preview unavailable")
    return {"path": path, "size": info.st_size, "modified_at": info.st_mtime, "content": content}


def inspect_workspace(root, action, path="", after="", limit=100):
    components = parts(path)
    if action not in ("list", "read") or (action == "read" and not components):
        raise HTTPException(400, "Invalid read-only browser operation")
    if not 1 <= limit <= 200:
        raise HTTPException(400, "Invalid page size")
    try:
        with directory(root, components if action == "list" else components[:-1]) as fd:
            return listing(fd, path, after, limit) if action == "list" else read(fd, components[-1], path)
    except FileNotFoundError:
        raise HTTPException(404, "Entry no longer exists; refresh") from None
    except PermissionError:
        raise HTTPException(403, "Entry is not readable") from None
    except OSError:
        raise HTTPException(400, "Entry is unavailable or is an unsupported link or special file") from None
