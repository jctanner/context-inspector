# Context Inspector Overview

## Product question

Can a user interact with the actual Claude CLI while seeing, in near real time,
the effective context crossing the model API boundary?

## Proposed architecture

```text
browser
├── xterm.js terminal
└── context inspector
        │ WebSocket
local server
├── PTY bridge ─────────────── agent container / Claude CLI
├── event store and diff engine
└── live capture receiver ◄── mitmproxy sidecar ── model endpoint
```

The terminal and capture paths are deliberately independent. Terminal output
shows product behavior; intercepted HTTP traffic establishes what the model
actually received and returned.

## Product principles

1. Use the real CLI, not an agent SDK or a simulated chat interface.
2. Show exact captured data separately from normalized and inferred views.
3. Default to a structural diff against the preceding request in the same
   request stream.
4. Represent uncertain primary/subagent attribution with confidence and
   evidence, plus an unclassified stream.
5. Keep sensitive traffic local and ephemeral by default.

## Delivery phases

1. Observable session: terminal interaction and chronological live flows.
2. Context interpretation: readable decomposition and structural diffs.
3. Agent attribution: evidence-based stream grouping and tabs.
4. Specialized annotations: compaction, retries, memory, tools, and context
   window errors.
