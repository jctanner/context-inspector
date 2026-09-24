"""Per-launch Codex notify queue and bounded MLflow exporter. No host config writes.

The notify process only enqueues. The CLI supervisor owns exports and waits for
pending jobs on normal exit. SIGKILL/container force-removal cannot be drained.
"""
from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent
USAGE_KEYS = ("input_tokens", "output_tokens", "total_tokens")


def scoped_records(records: list[dict], turn_id: str) -> tuple[list[dict], str]:
    """Select by captured ID; never substitute the latest turn for a missing one."""
    start = end = None
    for i, row in enumerate(records):
        p = row.get("payload", {})
        if row.get("type") != "event_msg":
            continue
        if p.get("type") == "task_started" and p.get("turn_id") == turn_id:
            start, end = i, None
        elif start is not None and p.get("type") == "task_started":
            break
        elif start is not None and p.get("type") == "task_complete" and p.get("turn_id") == turn_id:
            end = i + 1
            break
    if start is None or end is None:
        return [], "unavailable"
    selected = copy.deepcopy(records[start:end])
    # Prefer this turn's context; getModel upstream otherwise chooses the first model.
    contexts = [r for r in records[:end] if r.get("type") == "turn_context" and r.get("payload", {}).get("model")]
    session_meta = next((r for r in records if r.get("type") == "session_meta"), None)
    if session_meta:
        selected.insert(0, copy.deepcopy(session_meta))
    if contexts:
        selected.insert(0, copy.deepcopy(contexts[-1]))
    def counter(row):
        p = row.get("payload", {})
        value = (p.get("info") or {}).get("total_token_usage") if p.get("type") == "token_count" else None
        return value if isinstance(value, dict) and all(type(value.get(k)) is int and value[k] >= 0 for k in USAGE_KEYS) else None
    before = [v for r in records[:start] if (v := counter(r)) is not None]
    during = [v for r in records[start:end] if (v := counter(r)) is not None]
    # A resumed/forked session may start with nonzero totals. Without an observed
    # baseline, report unknown instead of charging historical usage to this turn.
    baseline = before[-1] if before else None
    if baseline is None and during:
        p = next(r["payload"] for r in records[start:end] if counter(r) is not None)
        last = (p.get("info") or {}).get("last_token_usage", {})
        if all(last.get(k) == during[0][k] for k in USAGE_KEYS):
            baseline = dict.fromkeys(USAGE_KEYS, 0)
    usage = None
    if baseline is not None and during:
        counters = [baseline, *during]
        if all(b[k] >= a[k] for a, b in zip(counters, counters[1:]) for k in USAGE_KEYS):
            usage = {k: during[-1][k] - baseline[k] for k in USAGE_KEYS}
    for row in selected:
        p = row.get("payload", {})
        if p.get("type") == "token_count" and isinstance(p.get("info"), dict):
            p["info"].pop("last_token_usage", None)
    if usage is not None:
        selected.insert(-1, {"type": "event_msg", "timestamp": selected[-1].get("timestamp"),
                            "payload": {"type": "token_count", "info": {"last_token_usage": usage}}})
    return selected, "transcript cumulative counter delta" if usage is not None else "unavailable"


def read_turn(home: Path, thread: str, turn: str) -> tuple[list[dict], str]:
    # Restrict lookup to native rollout files; IDs never become filesystem paths.
    for path in (home / "sessions").glob("*/*/*/rollout-*.jsonl"):
        if not path.name.endswith(f"-{thread}.jsonl"):
            continue
        rows = []
        with path.open() as stream:
            for line in stream:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    break  # A concurrently appended final line is not complete yet.
        return scoped_records(rows, turn)
    return [], "unavailable"


def enqueue(queue: Path, raw: str) -> None:
    payload = json.loads(raw)
    if payload.get("type") != "agent-turn-complete":
        return
    if not all(isinstance(payload.get(k), str) and payload[k] for k in ("thread-id", "turn-id")):
        raise ValueError("Missing native notification IDs")
    key = hashlib.sha256((payload["thread-id"] + "\0" + payload["turn-id"]).encode()).hexdigest()
    # Atomic publication, duplicate notifications use the same queue key.
    with tempfile.NamedTemporaryFile(mode="w", dir=queue, delete=False) as stream:
        json.dump(payload, stream)
        temporary = Path(stream.name)
    temporary.replace(queue / (key + ".json"))


def export_job(path: Path, home: Path, previous: list[str], log_path: Path,
               shutdown_deadline: list[float | None]) -> None:
    def timeout(limit):
        deadline = shutdown_deadline[0]
        remaining = limit if deadline is None else min(limit, deadline - time.monotonic())
        if remaining <= 0:
            raise subprocess.TimeoutExpired("MLflow shutdown drain", limit)
        return remaining
    payload = json.loads(path.read_text())
    with log_path.open("ab") as log:
        # Preserve the original callback with its original payload and environment.
        if previous:
            try:
                subprocess.run([*previous, json.dumps(payload)], stdin=subprocess.DEVNULL,
                               stdout=log, stderr=log, start_new_session=True, timeout=timeout(10), check=True)
            except (OSError, subprocess.SubprocessError):
                log.write(b"Existing Codex notify failed or timed out.\n")
        try:
            records, usage = [], "unavailable"
            deadline = time.monotonic() + timeout(2)
            while time.monotonic() < deadline:
                records, usage = read_turn(home, payload["thread-id"], payload["turn-id"])
                if records:
                    break
                time.sleep(.05)
            with tempfile.TemporaryDirectory(prefix="codex-mlflow-turn-") as directory:
                snapshot = Path(directory)
                sessions = snapshot / ".codex" / "sessions" / "2000" / "01" / "01"
                sessions.mkdir(parents=True)
                # IDs in real callbacks are UUID/numeric, but do not interpolate
                # untrusted callback content into paths even in private tmpdirs.
                thread = payload["thread-id"]
                if not thread or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in thread):
                    raise ValueError("Invalid thread ID")
                if records:
                    (sessions / f"rollout-snapshot-{thread}.jsonl").write_text(
                        "".join(json.dumps(row) + "\n" for row in records))
                metadata = {"codex.turn_id": payload["turn-id"], "codex.thread_id": thread,
                            "context_inspector.evidence": "transcript reconstruction" if records else "notify only",
                            "context_inspector.usage_source": usage}
                metadata["codex.client"] = str(payload.get("client", "unknown"))
                session_meta = next((r["payload"] for r in records if r.get("type") == "session_meta"), {})
                if "source" in session_meta:
                    metadata["codex.session_source"] = json.dumps(session_meta["source"])
                inspector_session = os.environ.get("CONTEXT_INSPECTOR_SESSION_ID")
                if inspector_session:
                    metadata["context_inspector.session_id"] = inspector_session
                job = snapshot / "job.json"
                job.write_text(json.dumps({"payload": payload, "metadata": metadata}))
                subprocess.run(["node", str(ROOT / "codex-export.mjs"), str(job)],
                               env={**os.environ, "HOME": directory, "CODEX_HOME": str(snapshot / ".codex"),
                                    "MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false"},
                               stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, timeout=timeout(20), check=True)
        except (OSError, ValueError, subprocess.SubprocessError):
            # Never put potentially sensitive exception text into the terminal.
            log.write(b"Codex MLflow export failed; this turn may be missing.\n")
            print("MLflow: Codex export failed; see private mlflow-tracing.log.", file=sys.stderr)


def existing_notify(home: Path, argv: list[str]) -> list[str]:
    config = home / "config.toml"
    data = tomllib.loads(config.read_text()) if config.exists() else {}
    previous = data.get("notify", [])
    # Codex's notify is top-level (not a profile option). CLI overrides and
    # project-layer notify need explicit reconciliation, not silent replacement.
    overrides = []
    args = iter(argv[1:])
    for arg in args:
        if arg == "--":
            break
        if arg in {"-c", "--config"}:
            overrides.append(next(args, ""))
        elif arg.startswith("--config="):
            overrides.append(arg[len("--config="):])
        elif arg.startswith("-c"):
            overrides.append(arg[2:])
    if any(value.split("=", 1)[0].strip(" \t\"'") == "notify" for value in overrides):
        raise ValueError("Remove the command-line notify override before enabling MLflow")
    for directory in [Path.cwd(), *Path.cwd().parents]:
        path = directory / ".codex" / "config.toml"
        if path.exists() and path.resolve() != config.resolve():
            if "notify" in tomllib.loads(path.read_text()):
                raise ValueError("Project notify config cannot be safely chained; move it to inspector CODEX_HOME/config.toml")
    if not isinstance(previous, list) or any(not isinstance(v, str) for v in previous):
        raise ValueError("Codex notify must be an argv array")
    return previous


def supervise(argv: list[str]) -> int:
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    previous = existing_notify(home, argv)
    log_path = home / "mlflow-tracing.log"
    log_path.touch(mode=0o600, exist_ok=True)
    log_path.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix="codex-mlflow-queue-") as directory:
        queue = Path(directory)
        notify = [sys.executable, str(Path(__file__).resolve()), "notify", directory]
        # Installed Codex requires config on the innermost exec/resume
        # subcommand. Interactive launches take it directly after the executable.
        position = 1
        if len(argv) > 1 and argv[1] in {"exec", "resume"}:
            position = 2
            if len(argv) > 2 and argv[1:3] == ["exec", "resume"]:
                position = 3
        child = subprocess.Popen([*argv[:position], "-c", "notify=" + json.dumps(notify), *argv[position:]])
        # SIGINT is already delivered to the terminal process group. Forward
        # TERM/HUP to Codex, then allow pending exports to drain normally.
        def forward(signum, _frame):
            if signum != signal.SIGINT and child.poll() is None:
                child.send_signal(signum)
        old = {s: signal.signal(s, forward) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        seen, futures = set(), []
        shutdown_deadline = [None]
        exited = None
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                while True:
                    for path in queue.glob("*.json"):
                        if path.name not in seen:
                            seen.add(path.name)
                            futures.append(executor.submit(export_job, path, home, previous, log_path, shutdown_deadline))
                    if child.poll() is not None:
                        if exited is None:
                            exited = time.monotonic()
                            shutdown_deadline[0] = exited + 35
                        # Native notify is spawned, not awaited. Allow its short
                        # enqueue process to finish even after CLI exit.
                        if time.monotonic() - exited >= 1 and all(f.done() for f in futures):
                            break
                    time.sleep(.05)
                for future in futures:
                    try:
                        future.result()
                    except Exception:
                        # Unexpected transcript/queue shapes must not change the
                        # interactive CLI's exit status or disclose payloads.
                        with log_path.open("a") as log:
                            log.write("Codex MLflow job failed; trace may be missing.\n")
                        print("MLflow: Codex export failed; see private mlflow-tracing.log.", file=sys.stderr)
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
        code = child.wait()
        return code if code >= 0 else 128 - code


if __name__ == "__main__":
    os.umask(0o077)
    try:
        if sys.argv[1] == "notify":
            enqueue(Path(sys.argv[2]), sys.argv[3])
        elif sys.argv[1] == "run":
            sys.exit(supervise(sys.argv[2:]))
        else:
            raise ValueError("Unknown tracing command")
    except (OSError, ValueError) as error:
        print(f"Codex tracing configuration failed: {error}", file=sys.stderr)
        sys.exit(1)
