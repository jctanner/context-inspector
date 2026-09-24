# Nonzero agent exit skips capture archive export

Discovered during task 082 runtime review, 2026-09-23. `run.sh` uses `set -e` and
exports the capture archive only after the foreground agent returns successfully.
A failed CLI exits before export; cleanup then removes the proxy container and
its archive. Preserve the CLI exit code while exporting captured evidence.

## Resolution

Runtime preserves nonzero agent status while exporting capture; fake-Podman failure regression passes.
