# ADR-0042: Prefer the executing Codex runtime's model catalog

Accepted, 2026-09-23, task 088.

After moving harness installations into the image, the start dialog should use
container/home/evaluator/.codex/models_cache.json. The host cache is only a
bootstrap fallback when that file does not exist. An existing empty/unreadable
inspector cache must not silently revive choices from the host. Both profile
listing and launch validation use the same selection rule; API model_source
identifies which catalog was used. No fixed GPT-6 allowlist or cache edits.

Catalog entries are advertised choices, not confirmed account entitlement.
Refreshing the inspector catalog can change choices; do not merge historical
entries simply to retain desired names. This changes model discovery only, not
native credential sharing, wire interpretation or session state.
