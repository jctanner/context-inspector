// Synthetic first-request fixture: large arrays, nesting, safe labels and layout.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (v, message) => { if (!v) throw new Error(message); };
  const payload = {
    system: [{ type: "text", text: "System fixture" }],
    messages: Array.from({ length: 205 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: `Message fixture ${i}` })),
    tools: [{ name: "Bash", input_schema: { type: "object", properties: {} } }],
    '<img src=x onerror=alert(1)>': null,
  };
  const event = { kind: "context.diff", flow_id: "outline", sequence: 1, request_number: 1,
    cursor: 1, detail_url: "/api/sessions/fixture/context-details/outline/request", body_digest: "fixture",
    predecessor_flow_id: null, predecessor_basis: "first_request", predecessor_confidence: "none",
    stream_identity: { stream_id: "unclassified", confidence: "none", evidence: [] },
    request_purpose: { classification: "unclassified", confidence: "none", evidence: [] },
    comparison_lineage: "unclassified", relationship: "chronological",
    counts: { added: 1, removed: 0, transformed: 0, retained: 0 },
    metrics: { body_bytes: 20000, previous_body_bytes: null, token_count: null }, changes: [],
    exact_request: { body: { decoded: { value: payload } } } };
  let baseline;
  try {
    await context.route("**/api/sessions/active", route => route.fulfill({ json: { session_id: "fixture", alive: true } }));
    await context.route("**/api/sessions/fixture/context-history?*", route => route.fulfill({ json: {
      events: [event], cursor: 1, total: 1, next_before: null, latest_usage: null,
    } }));
    await context.route("**/api/sessions/fixture/context-details/**", route => route.fulfill({ json:
      route.request().url().endsWith("/baseline/request")
        ? { exact_request: { body: { decoded: { value: baseline } } } }
        : { ...event, detail_url: undefined } }));
    await context.routeWebSocket("**/api/sessions/fixture/terminal", () => {});
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => ws.send(JSON.stringify({ type: "context-batch", events: [], cursor: 1 })));
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    await view.locator(".inspect-request").click();
    const outline = view.getByRole("navigation", { name: "Payload outline", exact: true });
    await outline.waitFor();
    const root = outline.getByRole("button", { name: "Request payload · 4 fields", exact: true });
    await root.click();
    check(await root.getAttribute("data-path") === "", "readable root must retain root JSON Pointer");
    check(await view.locator(".payload-target .line-number").nth(1).innerText() === "1", "root jump must still target first payload line");
    check(await outline.locator('option[value="Before"]').evaluate(el => el.disabled), "first request must disable absent Before outline");
    check(await outline.locator("img").count() === 0, "outline keys must remain literal text");
    check(await outline.locator(".payload-outline-link").count() === 5, "nested children must be lazy");
    const outlineBounds = await outline.boundingBox(), tableBounds = await view.locator(".payload-diff").boundingBox();
    check(outlineBounds.x + outlineBounds.width < tableBounds.x, "wide outline must sit left of diff");
    const expand = async text => {
      await outline.locator("summary").filter({ hasText: text }).focus();
      await view.keyboard.press("Enter");
    };
    await expand("messages");
    await outline.getByRole("button", { name: "Show more (105 remaining)", exact: true }).waitFor();
    check(await outline.locator('[data-path="/messages/100"]').count() === 0, "large branches must be paged");
    await outline.getByRole("button", { name: "Show more (105 remaining)", exact: true }).click();
    await outline.getByRole("button", { name: "Show more (5 remaining)", exact: true }).click();
    await outline.locator('[data-path="/messages/204"]').click();
    const targetBounds = await view.locator(".payload-target").boundingBox();
    check(targetBounds.y > 0 && targetBounds.y < 800, "jump must scroll the target into view");
    check(await outline.locator('[aria-current="location"]').getAttribute("data-path") === "/messages/204", "selected node must be indicated");
    await expand("tools");
    check((await outline.locator('[data-path="/tools/0"]').innerText()).includes("Bash"), "tool name must label the entry");
    await view.setViewportSize({ width: 390, height: 844 });
    const narrowOutline = await outline.boundingBox(), narrowTable = await view.locator(".payload-diff").boundingBox();
    check(narrowOutline.y + narrowOutline.height <= narrowTable.y, "mobile outline must stack above diff");
    check(await view.locator(".request-view").evaluate(el => el.scrollWidth <= el.clientWidth), "mobile request view must not overflow horizontally");
    // Separated hunks, including a message beyond the first two lazy pages.
    baseline = JSON.parse(JSON.stringify(payload));
    baseline.messages[0].content = "Old first message";
    baseline.messages[204].content = "Old last message";
    baseline['<img src=x onerror=alert(1)>'] = "Old tail";
    event.predecessor_flow_id = "baseline";
    event.exact_request.body.decoded.value = { added: "New field", ...payload };
    await view.setViewportSize({ width: 1280, height: 800 });
    await view.reload();
    await view.locator(".inspect-request").click();
    await outline.waitFor();
    const navigate = async (direction, path, expectedSide = "Before") => {
      const button = view.getByRole("button", { name: `${direction} change`, exact: true });
      await button.click();
      const current = outline.locator('[aria-current="location"]');
      check(await current.getAttribute("data-path") === path, `wrong outline path after ${direction}`);
      check(await current.isVisible(), "selected entry's ancestors must be expanded");
      check(await outline.getByLabel("Payload side").inputValue() === expectedSide, "hunk must select its observed payload side automatically");
      check(await button.evaluate(el => el === document.activeElement), "navigation must not steal keyboard focus");
      const entry = await current.boundingBox(), pane = await outline.boundingBox();
      check(entry.y >= pane.y && entry.y + entry.height <= pane.y + pane.height, "selected entry must be scrolled into outline viewport");
      const target = await view.locator(".payload-target").boundingBox();
      check(target.y > 0 && target.y < 800, "outline scrolling must not displace diff target");
    };
    await navigate("Previous", "/<img src=x onerror=alert(1)>");
    await navigate("Next", "/added", "After");
    await navigate("Next", "/messages/0/content");
    await navigate("Next", "/messages/204/content");
    await navigate("Next", "/<img src=x onerror=alert(1)>");
    // Previously populated branches can be closed manually and must reopen.
    await outline.locator("summary").filter({ hasText: "messages" }).focus();
    await view.keyboard.press("Enter");
    await navigate("Previous", "/messages/204/content");
    await outline.getByLabel("Payload side").selectOption("After");
    await navigate("Previous", "/messages/0/content");
    return { firstRequest: true, safeLabels: true, lazyChildren: true, pagedArrays: true, visibleJump: true, toolNames: true, responsiveLayout: true };
  } finally { await context.close(); }
}
