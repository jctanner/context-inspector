# Bug: Credential files under the Claude mirror can be read through the file browser

## Summary

The `/api/claude-files/file` route delegates to the generic workspace reader with
`CLAUDE_HOME / ".claude"` as its root. Hidden regular UTF-8 files are readable;
there is no credential-path exclusion. If OAuth credentials are stored or imported
there, the browser API can return them. This is a code-confirmed exposure path,
not evidence that credentials are currently present or have been accessed.

## Original reproduction

With a temporary fixture home, create `.claude/.credentials.json` containing a
synthetic sentinel, then call the route with `path=.credentials.json`. The reader
accepts that path and returns its content. Do not use real credentials to test.

## Expected

Credential material is outside browsable roots, or reads/listings explicitly deny
it server-side, including direct API requests.

## Original actual behavior

`src/server/app.py` and `src/server/workspace_files.py` allowed the read. Existing
`src/tests/test_claude_files.py` explicitly tests hidden-file access. The server
also defaults to 0.0.0.0; a hidden frontend entry would not protect the route.

## Resolution

The Claude files route now passes `.credentials.json` as a server-enforced
forbidden basename to the generic reader. Listings omit it and direct reads
return a non-disclosing 404. A synthetic fixture verified both behaviors. The
generic workspace browser remains unchanged.

## Impact

High if credential material is present in the mirrored directory. This is a
prerequisite for adding host OAuth credential reuse; no real secrets inspected.

## Related work

- Task 081: implemented the exclusion; task 082 tracks OAuth and Codex launch.
