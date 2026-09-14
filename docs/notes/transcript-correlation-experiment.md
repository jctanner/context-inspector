# Transcript-to-wire correlation experiment

Date: 2026-09-14. Scope: existing session, first 130 context requests. No new
Claude input, MLflow installation, hooks, runtime settings or UI behavior changes.

## Results

The main transcript contains 152 assistant records representing 64 distinct
response message IDs and 64 distinct request IDs. All 64 match captured requests
using both independent fields:

- transcript message.id = decoded response message ID;
- transcript requestId = captured response header request-id.

No conflicting scope matches; no unmatched unique transcript identifiers.
Repeated assistant records are collapsed by identifier, not counted as separate
model calls. All inspected assistant entries have isSidechain=false. There are
no subagent transcript files in this session, so subagent correlation remains
untested against real traffic (only synthetic collision handling is tested).

| Captured endpoint operation | Requests | Exact main-transcript matches |
| --- | ---: | ---: |
| streamRawPredict | 72 | 64 |
| Other model rawPredict | 31 | 0 |
| count-tokens:rawPredict | 27 | 0 |
| Total | 130 | 64 |

69 requests have derived context.response records; 64 join the transcript.
Unmatched derived responses are #14, #75, #83, #85, #93. #14 is heuristically
classified as likely title generation; the others remain unclassified. Do not
equate unmatched with helper/subagent or absent response with failed HTTP traffic:
the derived API does not expose every raw response, particularly token counts.

## Request 130

Request #130 joins the main transcript using both IDs. Its current baseline is
#128, whose captured URL explicitly targets count-tokens:rawPredict. All five
requests with a standalone foo block (#105, #107, #109, #126, #128) use that
token-count operation; the main transcript contains no such block.

This resolves the immediate ambiguity without MLflow: the baseline is a token
count request, not evidence that primary user text changed into a reminder.
The reason Claude sent those counting calls is not established here.

## Recommended follow-up (not implemented)

1. Classify API operation from captured URL before choosing context baselines.
   Preserve token-count traffic but separate it from model-generation histories.
2. Add a read-only transcript observer that correlates completed responses by
   exact identifiers, preserving source/evidence and collision handling.
3. Treat attribution as pending before response/transcript evidence arrives.
   Never assign a request merely because a subagent happened to be running.
4. Validate subagent joins with an explicitly authorized subagent experiment.
   Keep unmatched traffic separate rather than assuming it is primary or helper.
5. Repair positional block correspondence independently of request attribution.

## Reproduction

```bash
.venv/bin/python src/diagnostics/correlate_transcripts.py \
  --container magical_edison \
  --transcript /home/evaluator/.claude/projects/-workspace/9776f758-858f-4171-a46f-508022f3a214.jsonl
.venv/bin/python -m unittest src.tests.test_transcript_correlation
```

Use the current container/transcript path if the session changes. Diagnostic
reads captured evidence and transcripts in memory; output includes aggregates,
request numbers and IDs, but no prompt text, tool arguments, credentials or raw
transcript export. Capture pagination and transcript reads are not transactional;
results can grow or acquire delayed matches while Claude is active.
