# Bug: Codex terminal heading says Claude CLI

Starting or reconnecting a Codex session shows the static Claude CLI heading.
Expected: title follows active session harness. The status text already uses the
correct metadata. Tracked by task 083.

Fixed: connectSession updates heading and accessible label from harness metadata.
Build and mocked launch/reconnect browser checks pass (task 083).
