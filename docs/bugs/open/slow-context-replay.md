# Bug: Full Evidence Replay Makes Refresh Slow

Each viewer reconstructs the entire capture and downloads full request/response
evidence. Browser creates hidden block lists and measures layout on every event.
Task 036 introduces cached summaries, pagination and on-demand evidence.

Implementation and regression checks pass. Deployment awaits a server restart;
the current browser falls back to legacy replay until the API is available.
