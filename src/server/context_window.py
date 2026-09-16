"""Catalog-based context limits, separate from wire-observed token counts."""

import re
from urllib.parse import unquote, urlsplit


# Deployment defaults: user specifies Opus/Sonnet 4.6 at 200K in this stack.
# Deliberately bounded to the models offered by the session picker.
MODEL_WINDOWS = {
    "claude-haiku-4-5": 200_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 200_000,
}


def canonical_model(model: str) -> str:
    # API aliases, dated API/Vertex IDs and Bedrock regional inference IDs.
    model = re.sub(r"^(?:(?:us|eu|apac|global)\.)?anthropic\.", "", model)
    model = re.sub(r"(?:[-@][0-9]{8})?(?:-v[0-9]+:[0-9]+)?$", "", model)
    return model


def resolve_window(request: dict, *, override: int | None = None,
                   override_source: str = "configured override",
                   fallback_model: str | None = None) -> tuple[int, str]:
    if override is not None:
        return override, override_source
    payload = request.get("body", {}).get("decoded", {}).get("value", {})
    model = payload.get("model") if isinstance(payload, dict) else None
    evidence = "request body model"
    if not isinstance(model, str) or not model:
        path = unquote(urlsplit(request.get("url", "")).path)
        match = re.search(r"/(?:models|model)/([^/]+?)(?::(?:streamRawPredict|rawPredict|countTokens))?(?:/|$)", path)
        model = match[1] if match else None
        evidence = "request URL model"
    if not model:
        model, evidence = fallback_model, "launch model fallback; request model absent"
    canonical = canonical_model(model) if model else None
    if canonical in MODEL_WINDOWS:
        return MODEL_WINDOWS[canonical], f"deployment model default: {canonical} ({evidence}; not a wire-observed limit)"
    return 200_000, "fallback 200K: unknown or missing model; context limit unverified"
