# Bug: Default workspace exposes sibling repositories

Default Settings use PROJECT_ROOT.parent, which the runtime mounts read/write at
/workspace. Confirmed via running container mount metadata. Expected default is
PROJECT_ROOT/workspace. Related task: 037-local-workspace.

Default corrected and regression tests pass. Remains open until the running
server/container is replaced; the current container still has the old mount.
