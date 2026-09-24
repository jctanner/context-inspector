"""Server-owned harness/auth capabilities; unavailable profiles fail closed."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from .config import SESSION_MODELS, CLAUDE_HOME
from src.runtime.oauth import codex_cached_models


@dataclass(frozen=True)
class Profile:
    harness: str
    auth_mode: str
    label: str
    available: bool
    unavailable_reason: str | None
    models: tuple[str, ...]
    capture_profile: str
    capabilities: tuple[str, ...]


PROFILES = (
    Profile("claude", "vertex", "Claude · Vertex", True, None, SESSION_MODELS,
            "anthropic-http-v1", ("context", "usage", "claude_files", "mcp_dump", "skill_dump", "mlflow", "strace")),
    Profile("claude", "oauth", "Claude · OAuth", True, None,
            ("claude-haiku-4-5", "claude-sonnet-5"), "anthropic-http-v1", ("context", "usage", "claude_files")),
    Profile("codex", "oauth", "Codex · ChatGPT OAuth", True, None,
            (), "codex-responses-v1.1", ("context", "usage")),
)


def get_profile(harness: str, auth_mode: str) -> Profile:
    for profile in PROFILES:
        if (profile.harness, profile.auth_mode) == (harness, auth_mode):
            if harness == "codex":
                inspector_home = CLAUDE_HOME / ".codex"
                # Once the inspector has its own catalog, host updates must not
                # alter its picker. Do not revive a valid empty catalog via fallback.
                models = (codex_cached_models(inspector_home)
                          if (inspector_home / "models_cache.json").exists() else codex_cached_models())
                return replace(profile, models=models, available=bool(models),
                               unavailable_reason=None if models else "No selectable models in the native Codex catalog. The inspector cache is preferred; before its first run, the host cache supplies launch options.")
            return profile
    raise ValueError("Unsupported harness/auth combination")


def catalog(command_override: bool = False) -> dict:
    profiles = []
    for template in PROFILES:
        profile = get_profile(template.harness, template.auth_mode)
        item = asdict(profile)
        item["model_source"] = (("native inspector model cache" if (CLAUDE_HOME / ".codex/models_cache.json").exists() else "native host model cache (bootstrap fallback)") if profile.harness == "codex" else
                                "validated launch / host-reported model" if profile.auth_mode == "oauth" else "deployment catalog")
        if command_override:
            item.update(available=False, unavailable_reason="Profile selection is unavailable with a command override")
        profiles.append(item)
    return {"profiles": profiles, "default": {"harness": "claude", "auth_mode": "vertex", "model": SESSION_MODELS[0]}}
