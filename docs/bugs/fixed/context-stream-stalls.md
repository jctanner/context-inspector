# Bug: Context Stream Can Stall or Skip an Incomplete Record

Browser context sockets have no close/reconnect handling, and terminal status
can hide their failure. Both event readers advance their offsets past incomplete
JSONL lines written concurrently by the proxy, permanently skipping those bytes
until replay. Task 035 adds recovery/status and complete-record tailing.

Source fix verified by Python and browser regressions. Frontend recovery is built
and served. Server reader fix takes effect at the next server restart.
