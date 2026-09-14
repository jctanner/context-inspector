# Bug: Persistent Claude mount targets the wrong home

Runner binds .state/claude/config to /home/runner/.claude, but the active image's
UID 1000 uses /home/evaluator. Auto-memory and transcripts in the actual home
are therefore in the disposable container layer, not the advertised persistent
directory. Preserve any live container state before recreating it.
Task 054 changes to an explicit project-local evaluator-home mirror.

Fixed by task 054; mount smoke test verified UID 1000 sees the evaluator home
and mirrored configuration. Runtime rejects incompatible image home paths.
Old ephemeral home was already gone when the user stopped the previous stack;
the old empty persistent config and workspace were preserved, not reconstructed.
