# Missing Codex code-mode execution host

The runtime mounts only the native codex binary. The installed package also ships
codex-code-mode-host; its absence prevents interactive workspace execution.
Earlier noninteractive tool probes did not cover this interactive execution path.
Tracked in task 086.

Fixed by task 086: mount matching adjacent helper and fail early on incomplete
installation. Synthetic mount/preflight tests and isolated helper startup pass.
