# ADR-0028: Dynamic stdio MCP experiment

## Status

Accepted.

## Decision

Run a standard-library Python script as a Claude-owned stdio MCP subprocess.
Read-only mount its source and supply `--mcp-config` without strict mode, preserving
other configured servers. No HTTP service, SDK installation or stack container
is needed. The existing base image has Python 3.13.14 (verified in isolation).

Watch `/workspace/.context/mcp-dump/config.json` once per second while a reader
thread waits for stdin. The main thread owns stdout, state updates and protocol
responses. Advertise `tools.listChanged`, then emit notifications only after
initialization. Implement the 2025-06-18 MCP version, ping, paginated tools/list,
and harmless tools/call; unsupported requests receive JSON-RPC errors.

Start with one tool, exclusively create missing configuration, and retain the
last valid configuration on invalid edits or missing files. An initially invalid
file produces an empty list until corrected. Zero tools explicitly clears the
inventory. Stable per-tool seeds prevent count changes from changing surviving
definitions. Cursors identify the configuration and reject stale pagination.
Originally bounded inputs and aggregate metadata. ADR-0029 removes count and
aggregate-size caps at the user's request; other file-managed limits remain.

## Consequences

One initial user-managed restart activates the new mount and MCP configuration.
Later config edits need no restart. Dummy calls never execute commands, perform
network requests, read model-specified paths or echo arguments. Configuration
persists in the already-ignored workspace and is not reset with Claude history.
Diagnostics use stderr exclusively. Claude may defer schemas, so advertised
tool count is not evidence of model-visible context growth.
