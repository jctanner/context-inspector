# Bug: Browser Requests a Missing Favicon

## Observed

During the 2026-08-19 headless Chrome validation, the server returned `404` for
`GET /favicon.ico`.

## Impact

The application remains usable, but every browser load produces avoidable
server-log noise and a missing-site-icon request.

## Evidence

Uvicorn access log from the Task 004 visual validation at 1600×1000.

## Suggested fix

Add a small project-owned icon under `src/web/` and reference it explicitly in
`index.html`.
