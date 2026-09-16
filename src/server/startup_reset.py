"""Once-per-stack, allowlisted cleanup of the fixed Claude home mirror."""

from contextlib import ExitStack, contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

from .config import PROJECT_ROOT


RESET_ENTRIES = (
    "projects", "agent-memory", "file-history", "history.jsonl",
    "sessions", "session-env", "shell-snapshots", "cache", "debug",
    "plans", "tasks", "todos", "paste-cache", "image-cache",
)
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def assert_home_unused(home: Path) -> None:
    """Fail closed, including older containers that have no inspector labels."""
    result = subprocess.run(
        ["podman", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    for container_id in result.stdout.splitlines():
        info = subprocess.run(
            ["podman", "inspect", "--format", "{{json .State.Status}} {{json .Mounts}}", container_id],
            check=True, capture_output=True, text=True, timeout=15,
        )
        state, mounts = info.stdout.strip().split(" ", 1)
        if json.loads(state) in {"exited", "stopped", "configured"}:
            continue
        for mount in json.loads(mounts):
            if not mount.get("Source"):
                continue
            source = Path(mount["Source"]).resolve()
            if source == home or source in home.parents or home in source.parents:
                raise RuntimeError(
                    f"Refusing Claude startup reset: container {container_id[:12]} still uses the home. "
                    "Stop the previous stack/Claude container first."
                )


def _open_child(stack: ExitStack, parent: int, name: str) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent)
    except FileExistsError:
        pass
    descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    stack.callback(os.close, descriptor)
    return descriptor


def _remove_entries(home_fd: int, names=RESET_ENTRIES, label="Claude") -> list[str]:
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError("Claude startup reset requires symlink-resistant rmtree")
    removed = []
    for name in names:
        try:
            entry = os.stat(name, dir_fd=home_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(entry.st_mode):
            shutil.rmtree(name, dir_fd=home_fd)
        else:
            # Unlink symlinks themselves; never traverse their targets.
            os.unlink(name, dir_fd=home_fd)
        removed.append(name)
        print(f"{label} startup reset: removed {name} (permanent; no backup)", flush=True)
    return removed


def _assert_no_mounted_targets(home: Path, *, entire_root: bool = False) -> None:
    # rmtree does not follow symlinks, but would traverse an actual bind mount.
    # Refuse these before deleting any entry. Linux/Podman is the supported runtime.
    targets = [home] if entire_root else [home / name for name in RESET_ENTRIES]
    protected_roots = {home, *(p for p in home.parents if PROJECT_ROOT in p.parents)}
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        encoded = line.split()[4]
        mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), encoded))
        if mount in protected_roots or any(mount == target or target in mount.parents for target in targets):
            raise RuntimeError("Refusing Claude startup reset: a cleanup entry contains a mounted filesystem")


def clear_session_traces() -> None:
    """Clear only traces; caller owns the stack lifetime and session lifecycle locks."""
    with ExitStack() as stack:
        project_fd = os.open(PROJECT_ROOT, DIRECTORY_FLAGS)
        stack.callback(os.close, project_fd)
        container_fd = _open_child(stack, project_fd, "container")
        trace_fd = _open_child(stack, container_fd, "strace")
        root = PROJECT_ROOT / "container" / "strace"
        assert_home_unused(root)
        _assert_no_mounted_targets(root, entire_root=True)
        os.fchmod(trace_fd, 0o700)
        _remove_entries(trace_fd, os.listdir(trace_fd), "Strace")


@contextmanager
def clean_claude_startup(*, enabled: bool = True):
    if not enabled:
        yield
        return
    with ExitStack() as stack:
        project_fd = os.open(PROJECT_ROOT, DIRECTORY_FLAGS)
        stack.callback(os.close, project_fd)
        container_fd = _open_child(stack, project_fd, "container")
        lock_fd = os.open(".claude-startup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                          0o600, dir_fd=container_fd)
        stack.callback(os.close, lock_fd)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
            raise RuntimeError("Unsafe Claude startup lock file")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another stack owns this Claude home; stop it before restarting") from error
        home_parent_fd = _open_child(stack, container_fd, "home")
        evaluator_fd = _open_child(stack, home_parent_fd, "evaluator")
        home_fd = _open_child(stack, evaluator_fd, ".claude")
        home = PROJECT_ROOT / "container" / "home" / "evaluator" / ".claude"
        trace_fd = _open_child(stack, container_fd, "strace")
        trace_root = PROJECT_ROOT / "container" / "strace"
        assert_home_unused(home)
        assert_home_unused(trace_root)
        _assert_no_mounted_targets(home)
        _assert_no_mounted_targets(trace_root, entire_root=True)
        # Validate both roots before deleting either. The same lifetime lock owns both.
        os.fchmod(trace_fd, 0o700)
        _remove_entries(trace_fd, os.listdir(trace_fd), "Strace")
        removed = _remove_entries(home_fd)
        if not removed:
            print("Claude startup reset: no prior session data or memories to remove", flush=True)
        # Keep the advisory lock until the server and its terminal sessions exit.
        yield
