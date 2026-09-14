// Isolated synthetic APIs: no real memory contents, terminal input or mutations.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (value, message) => { if (!value) throw new Error(message); };
  const path = "projects/-workspace/memory/MEMORY.md";
  let lists = 0, reads = 0, sockets = 0, terminal, failure = false, empty = false, deleted = false;
  let revision = "# Memory fixture\n<img src=x onerror=alert(1)>\n[remote](https://example.invalid/image.png)";
  const record = { path, size: 99, modified_at: 1750000000 };
  const diff = { kind: "context.diff", flow_id: "memory-fixture", request_number: 1, sequence: 1, cursor: 1,
    detail_url: "/api/sessions/fixture/context-details/memory-fixture/request", predecessor_flow_id: null,
    predecessor_basis: "first_request", predecessor_confidence: "none", request_operation: "stream_generation",
    stream_identity: { stream_id: "unclassified", confidence: "none", evidence: [] },
    request_purpose: { classification: "unclassified", confidence: "none", evidence: [] },
    comparison_lineage: "unclassified", relationship: "chronological", body_digest: "fixture",
    counts: { added: 1, removed: 0, transformed: 0, retained: 0 }, metrics: { body_bytes: 20, token_count: null },
    changes: [], exact_request: { body: { decoded: { value: { text: "Fixture" } } } } };
  try {
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: { session_id: "fixture", alive: true } }));
    await context.route("**/api/sessions/fixture/context-history?*", route => route.fulfill({ json: { events: [diff], cursor: 1, total: 1, next_before: null, latest_usage: null } }));
    await context.route("**/api/sessions/fixture/context-details/**", route => route.fulfill({ json: { ...diff, detail_url: undefined } }));
    await context.route("**/api/sessions/fixture/memory", route => {
      lists++; check(route.request().method() === "GET", "memory listing must be read-only");
      return route.fulfill(failure ? { status: 503, json: { detail: "Memory fixture unavailable" } } : {
        json: { files: empty ? [] : [record], truncated: false, source: "Project-local mirror fixture" },
      });
    });
    await context.route("**/api/sessions/fixture/memory/file?*", route => {
      reads++; check(route.request().method() === "GET", "memory reading must be read-only");
      check(route.request().url().endsWith(`?path=${encodeURIComponent(path)}`), "file path must be encoded exactly");
      return route.fulfill(deleted ? { status: 404, json: { detail: "Memory file unavailable" } } : { json: { ...record, content: revision } });
    });
    await context.routeWebSocket("**/api/sessions/fixture/terminal", ws => { terminal = ws; sockets++; ws.send("fixture terminal"); });
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => { sockets++; ws.send(JSON.stringify({ type: "context-batch", events: [], cursor: 1 })); });
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    await view.locator("#flow-count").filter({ hasText: "1 request" }).waitFor();
    check(lists === 0 && reads === 0, "memory must not load eagerly in Session");
    await view.locator(".inspect-request").click();
    await view.locator(".payload-outline").waitFor();
    await view.getByRole("button", { name: "Memory", exact: true }).click();
    await view.getByRole("button", { name: "MEMORY.md", exact: true }).waitFor();
    check(await view.locator("#session-section").isHidden(), "Memory must replace Session without destroying it");
    check(await view.locator("#nav-memory").getAttribute("aria-current") === "page", "main navigation must indicate active section");
    await view.getByRole("button", { name: "MEMORY.md", exact: true }).focus();
    await view.keyboard.press("Enter");
    await view.locator("#memory-content").filter({ hasText: "Memory fixture" }).waitFor();
    check(await view.locator("#memory-content").innerText() === revision, "viewer must preserve exact source text");
    check(await view.locator("#memory-section img, #memory-content a, #memory-section textarea, #memory-section input").count() === 0, "memory must not execute markup, fetch assets or expose editing controls");
    check((await view.locator("#memory-file-meta").innerText()).includes("99 bytes"), "viewer must show file metadata");
    await view.getByRole("button", { name: "Session", exact: true }).click();
    check(await view.getByRole("tab", { name: "Request #1", exact: true }).getAttribute("aria-selected") === "true", "request tabs must survive section changes");
    await view.getByRole("button", { name: "Memory", exact: true }).click();
    check(lists === 1 && reads === 1 && sockets === 2, "section switches must reuse memory and live connections");
    revision = "# Updated fixture";
    await view.getByRole("button", { name: "Refresh memory", exact: true }).click();
    await view.locator("#memory-content").filter({ hasText: "Updated fixture" }).waitFor();
    deleted = true;
    await view.getByRole("button", { name: "MEMORY.md", exact: true }).click();
    await view.locator("#memory-file-meta").filter({ hasText: "Memory file unavailable" }).waitFor();
    check(await view.locator("#memory-content").innerText() === "", "failed reads must clear stale source");
    failure = true;
    await view.getByRole("button", { name: "Refresh memory", exact: true }).click();
    await view.locator("#memory-status").filter({ hasText: "Memory fixture unavailable" }).waitFor();
    failure = false; empty = true;
    await view.getByRole("button", { name: "Refresh memory", exact: true }).click();
    await view.locator("#memory-status").filter({ hasText: "No supported memory files" }).waitFor();
    empty = false; deleted = false;
    await view.getByRole("button", { name: "Refresh memory", exact: true }).click();
    await view.getByRole("button", { name: "MEMORY.md", exact: true }).click();
    await view.locator("#memory-content").filter({ hasText: "Updated fixture" }).waitFor();
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "memory view must fit mobile width");
    terminal.send(JSON.stringify({ type: "exit", exit_code: 0 }));
    await view.locator("#memory-status").filter({ hasText: "No active Claude session" }).waitFor();
    check(await view.locator("#memory-content").innerText() === "", "session exit must clear sensitive displayed memory");
    return { readOnly: true, sourceSafety: true, lazyLoading: true, refresh: true, errors: true, empty: true, sessionExit: true, preservedRequestTabs: true, singleLiveConnections: true, mobile: true };
  } finally { await context.close(); }
}
