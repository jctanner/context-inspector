"""Bounded, literal, read-only search of the fixed syscall trace mirror."""

import os
from pathlib import Path
import stat
import time

from fastapi import HTTPException

from .workspace_files import directory, FLAGS

MAX_BYTES = 128 * 1024 * 1024
MAX_LINE = 64 * 1024
MAX_RESULTS = 500
MAX_ENTRIES = 10000
MAX_SECONDS = 5


def search_traces(root: Path, query: str):
    if not query or len(query) > 1024 or "\x00" in query or "\n" in query or "\r" in query:
        raise HTTPException(400, "Enter 1–1024 characters of single-line literal text")
    needle = query.encode("utf-8")
    matches = []
    reasons = set()
    scanned = files = entries = 0
    deadline = time.monotonic() + MAX_SECONDS
    stopped = False

    def budget():
        nonlocal stopped
        if scanned >= MAX_BYTES:
            reasons.add("128 MiB scan limit reached")
            stopped = True
        if time.monotonic() >= deadline:
            reasons.add("5 second scan limit reached")
            stopped = True
        return not stopped

    def walk(fd, prefix="", depth=0):
        nonlocal scanned, files, entries, stopped
        with os.scandir(fd) as listing:
            for entry in listing:
                if not budget():
                    break
                entries += 1
                if entries > MAX_ENTRIES:
                    reasons.add("10,000 entry scan limit reached")
                    stopped = True
                    break
                path = f"{prefix}/{entry.name}" if prefix else entry.name
                try:
                    path.encode("utf-8")
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= 32 or info.st_dev != os.fstat(fd).st_dev:
                            reasons.add("Nested mount or directory depth limit skipped")
                            continue
                        child = os.open(entry.name, FLAGS, dir_fd=fd)
                        try:
                            walk(child, path, depth + 1)
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                        descriptor = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                        with os.fdopen(descriptor, "rb") as source:
                            current = os.fstat(source.fileno())
                            if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                                reasons.add("Changed or linked file skipped")
                                continue
                            files += 1
                            # Snapshot length: an actively growing log cannot keep a scan alive.
                            remaining = current.st_size
                            line_number = 0
                            continuation = False
                            while remaining and budget():
                                chunk = source.readline(min(MAX_LINE + 1, remaining, MAX_BYTES - scanned))
                                if not chunk:
                                    break
                                remaining -= len(chunk)
                                scanned += len(chunk)
                                if not continuation:
                                    line_number += 1
                                oversized = len(chunk) > MAX_LINE or continuation
                                continuation = not chunk.endswith(b"\n") and remaining > 0
                                if continuation and scanned >= MAX_BYTES:
                                    reasons.add("128 MiB scan limit reached")
                                    stopped = True
                                    break
                                if oversized:
                                    reasons.add("Lines over 64 KiB skipped")
                                    continue
                                if needle in chunk:
                                    matches.append({"path": path, "line": line_number,
                                                    "text": chunk.rstrip(b"\r\n").decode("utf-8", errors="replace")})
                                    if len(matches) >= MAX_RESULTS:
                                        reasons.add("500 match limit reached")
                                        stopped = True
                                        break
                    else:
                        reasons.add("Links or special files skipped")
                except (OSError, UnicodeError):
                    reasons.add("Unreadable or changed entry skipped")

    try:
        with directory(root, []) as fd:
            walk(fd)
    except FileNotFoundError:
        return {"matches": [], "files_scanned": 0, "bytes_scanned": 0, "partial": False,
                "warnings": [], "missing": True}
    except OSError:
        raise HTTPException(400, "Trace folder unavailable or an unsupported link") from None
    return {"matches": matches, "files_scanned": files, "bytes_scanned": scanned,
            "partial": bool(reasons), "warnings": sorted(reasons), "missing": False}
