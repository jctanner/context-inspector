# Task 088: Investigate missing GPT-6 choices in the start dialog

User reports GPT-6 Sol/Luna missing from Context Inspector's Start session dialog.
Running /api/profiles and both native catalogs include them. Reproduce the served
frontend options using read-only API calls and a mocked idle session; do not
start/stop or interact with the active CLI. Record evidence before changing code.


## Result

Could not reproduce in the currently served frontend. Read-only browser validation
against 127.0.0.1:8765, mocking only idle-session/unrelated API endpoints, obtained
all seven actual /api/profiles choices: gpt-6-astra, gpt-6-sol, gpt-6-luna,
gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.5. Both requested models select
successfully and enable confirmation. No session POST, stop, terminal interaction
or source change. Existing active session remains gpt-5.6-luna. Suggested reopen
or refresh and scroll above GPT-5.6 choices. The cause in the user's browser is
unconfirmed; do not label this a fixed defect or infer account entitlement.

## Reopened after user counter-evidence

User confirms a second browser still shows only GPT-6 Astra, with remaining
choices GPT-5.6. Earlier localhost result does not explain this. Requested exact
origin/port and label formatting to identify the actual surface. Repeated
localhost API response still includes Sol/Luna. Do not claim stale browser state
or a resolved issue without reproducing the user's view.


## Resolved evidence and fix

At the user's exact testbox:8765 URL, reproduced five choices missing GPT-6
Sol/Luna. Subsequent requests through hostname, LAN IP and localhost all agreed.
The difference was temporal, not hostname routing: host cache fetched_at changed
from 2026-09-24T01:55:11Z to 02:02:06Z and dropped those two entries. Inspector
0.156.1 cache from 01:54:45Z still contains both. Root cause in our integration:
selector reads the host cache even though the harness now runs from the image.
Why the upstream host catalog changed remains unknown.

Implemented inspector cache precedence, host bootstrap fallback only when the
inspector cache does not exist. Existing empty/invalid inspector metadata fails
closed; do not resurrect host options. Model listing and launch validation share
this rule. API provenance updated. No model names hard-coded or cache files edited.
ADR-0042 records the choice. Updated backend code now returns both GPT-6 models
from inspector metadata. Fourteen affected profile/runtime tests pass, including
host updates, inspector precedence, bootstrap and empty-list behavior.

Backend restart is required to activate. Did not restart the server, stop the
active Codex session, or claim service acceptance of these models. Previous stale
browser suggestion was unsupported; initial checks occurred before host refresh.
