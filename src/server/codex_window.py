"""Catalog-derived effective budgets; never a wire-observed context limit."""
import json
import os
from pathlib import Path


def read_catalog(path: Path) -> dict:
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            return {}
        data = json.loads(path.read_text())
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return {}
        result = {}
        for entry in models:
            if not isinstance(entry, dict):
                continue
            model, window, percent = (entry.get(key) for key in
                                      ("slug", "context_window", "effective_context_window_percent"))
            if (not isinstance(model, str) or not model or type(window) is not int
                    or window <= 0 or type(percent) is not int or not 0 < percent <= 100):
                continue
            if model in result:
                result[model] = None  # Conflicting or duplicate entries are ambiguous.
                continue
            effective = window * percent // 100
            if effective > 0:
                result[model] = {"tokens": effective, "source":
                    f"native Codex catalog default: {model}, {window} × {percent}% "
                    f"(cache fetched {data.get('fetched_at', 'unknown')}; not a wire-observed limit; "
                    "runtime overrides may differ)"}
        return {key: value for key, value in result.items() if value is not None}
    except (OSError, ValueError):
        return {}


def session_catalog(directory: Path, cache: Path) -> dict:
    """Freeze metadata at first inspection, including absence, for stable replay."""
    path = directory / "codex-context-windows.json"
    if path.exists():
        try:
            value = json.loads(path.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}
    value = read_catalog(cache)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle)
    except FileExistsError:
        return session_catalog(directory, cache)
    return value


def usage_window(request: dict, used: int | None, catalog: dict,
                 override: int | None, override_source: str) -> dict:
    value = request.get("body", {}).get("decoded", {}).get("value", {})
    model = value.get("model") if isinstance(value, dict) else None
    entry = catalog.get(model, {}) if isinstance(model, str) else {}
    entry = entry if isinstance(entry, dict) else {}
    window, source = override, override_source
    if window is None:
        window, source = entry.get("tokens"), entry.get("source", "unknown")
    if type(window) is not int or window <= 0:
        window, source = None, "unknown"
    return {"context_window_tokens": window, "context_window_source": source,
            "percent": min(100.0, used / window * 100) if used is not None and window else None}
