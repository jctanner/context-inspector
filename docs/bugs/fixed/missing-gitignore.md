# Bug: Missing root ignore rules expose local state

The deleted root .gitignore leaves .env, .state, .playwright-mcp, Python caches,
node_modules and frontend builds visible as untracked files. These can include
sensitive captured content and credentials. Task 040 restores and extends rules.

Resolved by the root .gitignore; positive and negative path tests pass. No
currently tracked files match these rules, so index cleanup is unnecessary.
