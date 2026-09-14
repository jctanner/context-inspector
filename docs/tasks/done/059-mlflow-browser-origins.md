# Task: Fix MLflow remote browser POST rejection

- [x] Add explicit browser-origin configuration without weakening Host checks.
- [x] Configure this installation's LAN/hostname/VPN origins; preserve loopback defaults.
- [x] Test real-container POSTs with allowed and rejected Origin headers.
- [x] Update documentation and hand off for user-managed restart.

Diagnosis: Host allowance alone permits page GETs but browser POSTs carrying
the LAN Origin receive 403. See docs/bugs/fixed/mlflow-browser-origin-403.md.

Verification: 12 MLflow tests pass including real-container POSTs returning 200
for the configured LAN origin, localhost and requests without Origin. Unrelated
and wrong-port origins return 403; unapproved Host is still rejected. DB/artifact
reset regression passes. 11 additional focused tests pass (one opt-in tracing
test skipped). Actual local .env configuration and whitespace check verified.
No active-stack restart or data modification; user will restart to activate.
