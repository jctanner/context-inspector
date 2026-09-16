"""Adjust only positively identified synthetic skill files; no recursive deletion."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import random
import re
import stat
import threading

from fastapi import HTTPException
from src.runtime.skill_dump.generator import write_skill


MARKER = b"Synthetic random-word skill for context-load testing."


@contextmanager
def directory(workspace, create=False):
    descriptors = []
    try:
        fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in (".context", "skill-dump", ".claude", "skills"):
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        yield fd
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


@contextmanager
def generated_folder(fd, name):
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    try:
        if os.listdir(child) != ["SKILL.md"]:
            raise HTTPException(409, f"Refusing to change {name}: unexpected files")
        descriptor = os.open("SKILL.md", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=child)
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise HTTPException(409, f"Refusing unsafe skill file in {name}")
            header = handle.read(4096)
        if not header.startswith(f"---\nname: {name}\ndescription: ".encode()) or MARKER not in header:
            raise HTTPException(409, f"Refusing to change {name}: not a generated skill")
        yield child, info
    finally:
        os.close(child)


def inventory(fd):
    names = []
    signature = hashlib.sha256()
    for name in sorted(os.listdir(fd)):
        if not re.fullmatch(r"skill-dump-[0-9]{4,}", name):
            continue
        if name != f"skill-dump-{int(name.removeprefix('skill-dump-')):04d}":
            continue
        with generated_folder(fd, name) as (_, info):
            names.append(name)
            signature.update(f"{name}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}\n".encode())
    return sorted(names, key=lambda name: int(name.removeprefix("skill-dump-"))), signature.hexdigest()


class SkillCount:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.worker = None
        self.state = {"skill_count": "0", "revision": hashlib.sha256().hexdigest(),
                      "running": False, "target_count": None, "error": None}

    def _refresh(self):
        try:
            with directory(self.workspace) as fd:
                names, revision = inventory(fd)
        except FileNotFoundError:
            names, revision = [], hashlib.sha256().hexdigest()
        self.state.update(skill_count=str(len(names)), revision=revision)

    def snapshot(self):
        with self.lock:
            if not self.state["running"]:
                try:
                    self._refresh()
                except OSError:
                    raise HTTPException(409, "Skill dump is unavailable or has an unsafe path") from None
            return dict(self.state)

    def start(self, count, revision):
        if type(count) is not int or count <= 0:
            raise HTTPException(422, "Enter a positive integer")
        with self.lock:
            if self.state["running"]:
                raise HTTPException(409, "Skill generation is already running. Wait or refresh.")
            current = self.snapshot()
            if revision != current["revision"]:
                raise HTTPException(409, "Skill files changed elsewhere. Refresh and try again.")
            self.state.update(running=True, target_count=str(count), error=None)
            self.stop.clear()
            self.worker = threading.Thread(target=self._run, args=(count, revision), daemon=True)
            self.worker.start()
            return dict(self.state)

    def _run(self, count, revision):
        error = None
        try:
            with directory(self.workspace, create=True) as fd:
                names, current_revision = inventory(fd)
                if current_revision != revision:
                    raise HTTPException(409, "Skill files changed elsewhere. Refresh and try again.")
                while len(names) > count and not self.stop.is_set():
                    name = names[-1]
                    with generated_folder(fd, name) as (child, info):
                        latest = os.stat("SKILL.md", dir_fd=child, follow_symlinks=False)
                        if (latest.st_ino, latest.st_mtime_ns) != (info.st_ino, info.st_mtime_ns):
                            raise HTTPException(409, "Skill changed during update; refresh")
                        os.unlink("SKILL.md", dir_fd=child)
                    os.rmdir(name, dir_fd=fd)
                    names.pop()
                    with self.lock:
                        self.state["skill_count"] = str(len(names))
                number = max((int(name.removeprefix("skill-dump-")) for name in names), default=0)
                rng = random.Random()
                while len(names) < count and not self.stop.is_set():
                    number += 1
                    name = f"skill-dump-{number:04d}"
                    os.mkdir(name, mode=0o755, dir_fd=fd)
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        descriptor = os.open(".generating", os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                             0o644, dir_fd=child)
                        try:
                            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                                write_skill(handle, name, rng)
                            os.link(".generating", "SKILL.md", src_dir_fd=child, dst_dir_fd=child)
                        finally:
                            os.unlink(".generating", dir_fd=child)
                    except BaseException:
                        try:
                            os.rmdir(name, dir_fd=fd)
                        except OSError:
                            pass
                        raise
                    finally:
                        os.close(child)
                    names.append(name)
                    with self.lock:
                        self.state["skill_count"] = str(len(names))
                if self.stop.is_set():
                    error = "Skill update interrupted by server shutdown; completed files remain."
        except HTTPException as exc:
            error = exc.detail
        except Exception:
            error = "Skill update failed; check file access or free disk space, then refresh. Completed changes remain."
        finally:
            with self.lock:
                self.state.update(running=False, error=error)
                try:
                    self._refresh()
                except (OSError, HTTPException):
                    self.state["error"] = error or "Could not recount skill files; refresh."

    def close(self):
        self.stop.set()
        if self.worker:
            self.worker.join()
