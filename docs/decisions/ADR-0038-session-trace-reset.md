# ADR-0038 — Reset strace before new frontend sessions

Extend ADR-0037: clear container/strace on real new-session creation as well as
stack startup. Stop and active-session joins preserve traces. Home state and
workspace are not reset by this operation; no backups are made.

The API validates launch arguments first, then runs the existing no-follow,
active-container and mount-guarded removal before spawning the terminal runner.
Cleanup failure returns 409 and prevents launch. Test/custom command overrides
skip the reset. A session lifecycle lock serializes Start and Stop, and is held
until an in-flight cleanup worker finishes even if its HTTP task is cancelled.
The normal stack still owns its lifetime filesystem lock. This is an API lifecycle
policy, not a new deletion side effect for standalone runtime script invocations.
