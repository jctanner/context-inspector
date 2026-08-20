# Request-Stream Identity Investigation

## Scope

This investigation re-examined the completed Phase 1–4 subagent analyses and
their underlying MITM captures. Labels in those analyses came from controlled
canaries and harness checkpoints, not from the headers being evaluated here.
Fourteen successful analysis files were included.

## Stable wire evidence

`x-claude-code-agent-id` is the only stable per-agent identifier found.

| phase | classified role | requests | agent-ID header present |
|---|---|---:|---:|
| 1 | parent | 15 | 0 |
| 1 | subagent | 6 | 6 |
| 2 | parent | 43 | 0 |
| 2 | subagent | 9 | 9 |
| 3 | parent | 50 | 1 |
| 3 | worker | 22 | 14 |
| 4 | parent | 191 | 0 |
| 4 | worker | 196 | 196 |

Within Phase 4, the header value matched the locally observed sidechain
`agent_id` and remained stable before and after worker compaction. Named-agent
and successful full-fork Phase 3 workers also had stable values.

The header proves a stable identified agent stream. Its spelling or value
format does not, by itself, prove whether that stream came from a named agent,
full-context custom agent, or another future mechanism.

## Counterexamples and ambiguous cases

- Forked-skill (`context: fork`) worker requests had no agent-ID header. They
  are indistinguishable from primary requests by identifier absence alone.
- One early Phase 3 full-fork attempt did not observe the intended feature. Its
  canary analyzer labeled an agent-ID-bearing request as parent. This is a
  counterexample to treating experimental semantic labels as transport truth.
- `x-claude-code-session-id` and `metadata.user_id` were shared by parent and
  worker requests in the same CLI session. They identify a broader session or
  user, not a logical agent stream.
- Phase 4 agent IDs appeared later in parent tool-result content. Message
  ancestry can corroborate delegation and return paths, but content occurrence
  alone does not establish which agent authored a request.
- System-prompt fingerprints separated controlled parent and worker requests,
  but worker compaction introduced another fingerprint and future harness
  versions can change prompts.
- Tool sets separated parent from named/forked workers in many runs, but
  full-context workers intentionally overlapped the parent's tool set.
- Timing showed nested parent/worker phases in these controlled runs. Parallel
  agents, retries, and unrelated provider calls make timing unsuitable as a
  stable identifier.

## Confidence model

- **High — identified agent:** exact non-empty `x-claude-code-agent-id`; group
  by its complete value and retain the supporting header path.
- **Manual — user assignment:** a user explicitly groups flows or assigns a
  label. Record this as manual provenance, not inferred certainty.
- **Low — heuristic suggestion:** system fingerprint, tool-set shape, message
  ancestry, and timing may suggest a cluster. Never silently use it as fact.
- **None — unclassified:** no stable identifier and no manual assignment. This
  is the required default; it must not be renamed “primary.”

## UI and persistence design

The eventual tab model should contain one tab per exact agent-ID value plus an
always-available **Unclassified** tab. Display values may be shortened, but the
exact value and evidence path remain inspectable.

Manual reassignment should store a local overlay keyed by immutable event or
flow IDs, with the chosen stream label, timestamp, and `provenance: manual`.
It must never rewrite captured events or archives. A reset action removes only
the overlay. Heuristic suggestions may be offered to the user but require an
explicit acceptance action.

## Current implementation

`src/server/identity.py` implements only the high-confidence header rule and
the unclassified fallback. Context diffs maintain independent predecessor
baselines for each identified agent ID and a separate low-confidence baseline
for unclassified traffic. The browser shows the stream ID and confidence.
Manual reassignment and tabs are designed here but intentionally not implied to
exist yet.
