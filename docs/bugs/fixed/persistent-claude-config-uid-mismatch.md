# Bug: Persistent Claude Configuration Has a UID Mapping Mismatch

## Observed

Claude reports `EACCES` while statting `/home/runner/.claude/settings.json`.

## Cause

The image runs Claude as UID/GID 1000, while plain `--userns=keep-id` maps the
host user at its numeric host UID. The private mode-0700 project bind mount is
therefore owned by UID 13437 as seen inside the container and correctly denies
UID 1000.

## Expected

Podman maps the host user to the image's `runner` UID/GID 1000, retaining
private host permissions and writable container access.

## Resolution

Both agent-image invocations now use
`--userns=keep-id:uid=1000,gid=1000`. A disposable real-image validation
confirmed UID/GID 1000 could stat and write the mode-0700 project-local mount
while the files remained owned by the invoking host user outside the namespace.

Fixed by task 013 on 2026-08-19.
