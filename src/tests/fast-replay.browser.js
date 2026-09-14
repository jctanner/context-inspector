// Playwright browser_run_code_unsafe filename; isolated synthetic APIs and sockets.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (v, message) => { if (!v) throw new Error(message); };
  const make = n => ({ kind: "context.diff", flow_id: `f${n}`, sequence: n * 10, request_number: n,
    cursor: n, detail_url: `/api/sessions/fixture/context-details/f${n}/request`, body_digest: `body${n}`,
    predecessor_flow_id: n === 1 ? null : `f${n-1}`, predecessor_basis: "session_chronology_unclassified", predecessor_confidence: "none",
    stream_identity: { stream_id: "unclassified", confidence: "none", evidence: [] },
    request_purpose: { classification: "unclassified", confidence: "none", evidence: [] }, comparison_lineage: "unclassified",
    relationship: "chronological", counts: { added: 1, removed: 0, transformed: 0, retained: 30 },
    metrics: { body_bytes: 100000, previous_body_bytes: 99999, token_count: null }, changes: [], exact_request: {} });
  const rows = Array.from({ length: 44 }, (_, i) => make(i + 1));
  let ws;
  let details = 0;
  let connections = 0;
  let terminals = 0;
  let failNext = false;
  const full = { ...make(44), detail_url: undefined, changes: [{ change: "transformed",
    before: { category: "messages", path: "messages/0/0", role: "user", kind: "text", value: { type: "text", text: "Previous content" } },
    after: { category: "messages", path: "messages/0/0", role: "user", kind: "text", value: { type: "text", text: "Fetched full content" } } }],
    exact_request: { body: { decoded: { value: { messages: [{ role: "user", content: "Fetched full content" }] } } } } };
  try {
    await context.route("**/api/sessions/active", route => route.fulfill({ json: { session_id: "fixture", alive: true } }));
    await context.route("**/api/sessions/fixture/context-history?*", route => {
      const before = route.request().url().includes("before=");
      return route.fulfill({ json: { events: before ? rows.slice(0, 19) : rows.slice(19), cursor: 44, total: 44, next_before: before ? null : 20, latest_usage: null } });
    });
    await context.route("**/api/sessions/fixture/context-details/**", route => {
      details++;
      if (failNext) { failNext = false; return route.fulfill({ status: 503, json: {} }); }
      const n = Number(route.request().url().match(/\/f(\d+)\//)[1]);
      return route.fulfill({ json: { ...full, flow_id: `f${n}`, request_number: n } });
    });
    await context.routeWebSocket("**/api/sessions/fixture/terminal", socket => { terminals++; socket.send("fixture"); });
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", socket => {
      ws = socket; connections++;
      const cursor = Number(socket.url().match(/[?&]cursor=(\d+)/)?.[1]);
      socket.send(JSON.stringify({ type: "context-batch", events: [], cursor }));
    });
    const view = await context.newPage();
    const start = Date.now();
    await view.goto("http://127.0.0.1:8765");
    await view.locator("#flow-count").filter({ hasText: "25 of 44" }).waitFor();
    check(await view.locator("#flow-events > li .event-sequence").first().innerText() === "Request 44", "latest request must appear first");
    check(details === 0, "initial history must not fetch evidence");
    check(await view.locator(".change-block").count() === 0, "collapsed summaries must not construct hidden block lists");
    const initialLoadMs = Date.now() - start;
    await view.locator("#flow-events").evaluate(el => { el.scrollTop = 20; });
    await view.locator("#flow-events > li").first().locator(".inspect-request").click();
    await view.locator(".readable-text").filter({ hasText: "Fetched full content" }).waitFor();
    check(await view.getByRole("tab", { name: "Request #44", exact: true }).getAttribute("aria-selected") === "true", "request tab must be selected");
    check(await view.locator("#workspace").isHidden(), "request view must replace the split pane");
    const panelBounds = await view.locator(".request-view:not([hidden])").boundingBox();
    check(panelBounds.width >= 1200, "request evidence should use full width");
    const beforeBounds = await view.locator(".request-view .before").boundingBox();
    const afterBounds = await view.locator(".request-view .after").boundingBox();
    check(afterBounds.x > beforeBounds.x && Math.abs(afterBounds.y - beforeBounds.y) < 2, "before and after should be side by side");
    check(await view.locator(".request-view .request-evidence").getAttribute("open") === null, "raw evidence remains collapsed");
    check(details === 1, "opening a summary must fetch only its own evidence");
    check(await view.locator("#flow-count").innerText() === "25 of 44 requests · newest first", "hydration must not alter request count");
    await view.getByRole("tab", { name: "Live session", exact: true }).click();
    check(await view.locator("#flow-events").evaluate(el => el.scrollTop) === 20, "live scroll must survive tab switch");
    await view.locator("#flow-events > li").first().locator(".inspect-request").click();
    check(details === 1 && await view.getByRole("tab", { name: "Request #44", exact: true }).count() === 1, "reopening selects the existing tab without fetching");
    await view.getByRole("tab", { name: "Live session", exact: true }).click();
    await view.locator("#flow-events > li").nth(1).locator(".inspect-request").click();
    await view.getByRole("button", { name: "Close Request #43", exact: true }).click();
    check(await view.getByRole("tab", { name: "Request #44", exact: true }).getAttribute("aria-selected") === "true", "closing active selects adjacent request");
    await view.getByRole("tab", { name: "Live session", exact: true }).click();
    await view.locator("#older-history").click();
    await view.locator("#flow-count").filter({ hasText: "44 of 44" }).waitFor();
    check(await view.locator("#flow-events > li .event-sequence").last().innerText() === "Request 1", "older history must append in reverse order");
    await view.locator("#capture-status").filter({ hasText: "connected" }).waitFor();
    await view.getByRole("tab", { name: "Request #44", exact: true }).click();
    ws.send(JSON.stringify({ type: "context-batch", events: [make(45)], cursor: 45 }));
    await view.getByRole("tab", { name: "Live session (1 new)", exact: true }).waitFor();
    check(connections === 1 && terminals === 1, "tabs must not create extra live connections");
    await view.getByRole("button", { name: "Close Request #44", exact: true }).click();
    check(await view.getByRole("tab", { name: "Live session", exact: true }).getAttribute("aria-selected") === "true", "last close returns to pinned live tab and clears badge");
    await view.locator("#flow-count").filter({ hasText: "45 of 45" }).waitFor();
    await view.locator("#flow-events > li").nth(1).locator(".inspect-request").click();
    await view.getByRole("tab", { name: "Request #44", exact: true }).waitFor();
    await view.getByRole("tab", { name: "Request #44", exact: true }).press("Delete");
    check(await view.locator("#view-tabs [role=tab]").count() === 1, "closed request can be reopened and keyboard-closed");
    failNext = true;
    await view.locator("#flow-events > li").first().locator(".inspect-request").click();
    await view.getByRole("button", { name: "Retry", exact: true }).click();
    await view.locator(".request-view .readable-text").filter({ hasText: "Fetched full content" }).waitFor();
    await view.getByRole("tab", { name: "Request #45", exact: true }).press("Home");
    check(await view.locator("#live-tab").getAttribute("aria-selected") === "true", "Home selects pinned live tab");
    await view.getByRole("button", { name: "Close Request #45", exact: true }).click();
    check(await view.locator("#live-tab").getAttribute("aria-selected") === "true", "closing inactive tab preserves active live view");
    check(await view.locator("#flow-events > li .event-sequence").first().innerText() === "Request 45", "live request must prepend");
    ws.close({ code: 1011, reason: "fixture" });
    await view.locator("#capture-status").filter({ hasText: "retrying" }).waitFor();
    await view.locator("#capture-status").filter({ hasText: "Context: connected" }).waitFor();
    check(connections === 2 && ws.url().includes("cursor=45"), "reconnect must resume committed cursor");
    check(await view.locator(".flow-event").count() === 45, "reconnect must not duplicate summaries");
    return { initialLoadMs, initialCards: 25, latestFirst: true, noEagerEvidence: true, lazyFetch: true, pagination: true, liveHandoff: true, reconnect: true, closableTabs: true, fullWidthComparison: true, singleLiveConnection: true, retryEvidence: true };
  } finally { await context.close(); }
}
