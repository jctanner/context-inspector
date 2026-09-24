# Codex picker reads unrelated host runtime catalog

After harnesses moved into the image, the picker continued reading host
CODEX_HOME/models_cache.json. During task 088 the host cache changed at
2026-09-24T02:02:06Z, removing GPT-6 Sol/Luna; the inspector-owned 0.156.1 cache
from 01:54:45Z still lists both. Initial successful checks preceded that change.
Prefer the inspector catalog, using host only before an inspector cache exists.
Do not infer account entitlement or why the host service catalog changed.

Fixed: inspector catalog precedence with host fallback only before first cache;
profile/API/runtime tests pass. Backend restart required.
