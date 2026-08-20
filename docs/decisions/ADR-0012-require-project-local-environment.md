# ADR-0012: Require a Project-Local Environment File

## Status

Accepted — 2026-08-20

## Decision

The top-level launcher requires `${project_dir}/.env`, exports its values, and
fails with an actionable error if that exact file is absent. It does not search
or source parent directories. A committed `.env.example` documents supported
settings; the real `.env` remains ignored.

## Rationale

Context Inspector is now a standalone repository. Depending implicitly on an
unrelated parent checkout makes startup non-portable and can silently select
the wrong provider or credentials. An explicit local boundary makes required
configuration discoverable and predictable.

## Consequences

- A fresh clone requires `cp .env.example .env` and local configuration before
  startup.
- Missing configuration fails before frontend build or server/container work.
- Credentials remain local and uncommitted.
