# ADR-0030: Generated skill count control

## Status

Accepted.

## Decision

Add a Generated skills count widget beside MCP tools. Manage only
`<workspace>/.context/skill-dump/.claude/skills/skill-dump-NNNN/SKILL.md` files
identified by the existing generator's name/header and synthetic marker.
Unrelated names are ignored; matched directories with extra files, foreign
content, symlinks, hardlinks or special files block mutation.

Reuse generation through src/runtime/skill_dump/generator.py, retaining
scripts/skill-maker.py as its existing CLI. New files keep the 500–5,000-line,
96-description-word and 20-body-word-per-line defaults. Preserve retained skills
byte-for-byte. Decreases permanently unlink excess generated files and remove
only their empty directories, highest numbers first; no recursive deletion,
backups or restoration (explicit user direction).

A background worker runs one job per app at a time; the widget polls current
count/progress and recovers in-flight status on page refresh. State is on-disk
inventory, never inferred Claude registration. Descriptor-relative no-follow
access, exclusive creation, revision checks and mutation headers protect paths
and avoid ordinary concurrent-editor overwrites. Concurrent external edits can
interrupt a partially completed job; completed changes remain and are recounted.
Shutdown stops between skills. No arbitrary count cap; generating large counts
can exhaust disk or consume substantial time. Other processes do not share the
in-process job lock; unsafe simultaneous file changes are rejected when detected.

## Consequences

User-managed restart activates API/shared generator. Browser refresh loads new
controls; no session prompts/restarts are automated. File changes may require
Claude discovery or /reload-skills; configured count is not model-visible tokens.
