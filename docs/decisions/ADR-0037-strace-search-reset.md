# ADR-0037 — Ephemeral strace mirror and read-only search

Normal stack startup permanently clears all entries in container/strace, under
the existing lifetime startup lock. Validate both cleanup roots and active/paused
container mount overlap before removing either home state or traces. Never follow
symlinks or traverse mounted cleanup targets. This supersedes ADR-0036's retention
across stack launches; append mode remains useful for PID reuse within a launch.

Expose only literal, case-sensitive search at a server-fixed root, not shell grep
or client-supplied filesystem roots. The /strace tab shows relative filenames,
line numbers and plain-text matches without requiring an active session. No-store
responses and no link following apply, as with the other file browsers.

Search is bounded to 500 matches, 128 MiB, five seconds, 10,000 entries and 32
directory levels. Lines over 64 KiB are skipped, with incomplete searches visibly
labeled. Serialize scans to protect server responsiveness. Logs are live evidence,
not atomic snapshots; refresh by submitting again. No regex execution, edits,
automatic polling, backups or container APIs. Large logs may need offline search.
