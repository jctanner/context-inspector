// Run with Playwright browser_run_code_unsafe(filename=absolute path), against
// a built app at http://127.0.0.1:8765. All session APIs/WebSockets are mocked
// in an isolated browser context; no Claude input or captures are used.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (value, message) => { if (!value) throw new Error(message); };
  let events;
  let replay = [];
  const connectionUrls = [];
  const block = text => ({ path: "messages/0/0", category: "messages", role: "user", kind: "text", value: { type: "text", text } });
  const diff = (number, text, repeat = false, lineage = "unknown") => ({
    kind: "context.diff", flow_id: `fixture-${number}`, sequence: number * 100,
    predecessor_flow_id: number === 1 ? null : `fixture-${number - 1}`,
    predecessor_basis: "session_chronology_unclassified", predecessor_confidence: "none",
    stream_identity: { stream_id: "unclassified", classification: "unclassified", confidence: "none", evidence: [] },
    request_purpose: { classification: "unclassified", confidence: "none", evidence: [] },
    comparison_lineage: lineage, relationship: repeat ? "retry_or_duplicate" : "chronological",
    counts: { added: repeat ? 0 : 1, removed: 0, transformed: 0, retained: repeat ? 1 : 0 },
    metrics: { body_bytes: 99, previous_body_bytes: null, token_count: null, token_count_source: null },
    changes: [{ change: repeat ? "retained" : "added", before: repeat ? block(text) : null, after: block(text) }],
    exact_request: { body: { decoded: { value: { messages: [{ role: "user", content: text }] } } } },
  });
  const reply = number => ({
    kind: "context.response", flow_id: `fixture-${number}`, sequence: number * 100 + 1,
    stream_identity: { stream_id: "unclassified", confidence: "none" },
    response: { model: "fixture", message_id: "fixture", stop_reason: "end_turn", output_tokens: 12,
      content_blocks: [{ type: "thinking", thinking: "Private fixture thought", signature: "SIGNATURE_FIXTURE" }, { type: "text", text: "A readable reply" }] },
    purpose: { classification: "unclassified", confidence: "none", evidence: [] }, exact_response: {},
  });
  try {
    await context.route("**/api/sessions/active", route => route.fulfill({ json: { session_id: "fixture", alive: true } }));
    await context.route("**/api/sessions/fixture/context-history?*", route => route.fulfill({ status: 404, json: {} }));
    await context.routeWebSocket("**/api/sessions/fixture/terminal", ws => { ws.send("fixture terminal"); });
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => {
      events = ws;
      connectionUrls.push(ws.url());
      for (const event of replay) ws.send(JSON.stringify(event));
    });
    const view = await context.newPage();
    const inspectLatest = async () => {
      await view.locator("#flow-events .inspect-request").last().click();
      await view.getByRole("button", { name: "Block inspection", exact: true }).click();
    };
    const closeEvidence = async () => {
      await view.locator("#view-tabs .tab-close").last().click();
    };
    await view.goto("http://127.0.0.1:8765");
    await view.locator("#status").filter({ hasText: "Claude connected" }).waitFor();
    await view.waitForFunction(() => document.querySelector("#flow-count").textContent === "0 requests");
    for (const event of [diff(1, "hello"), diff(2, "hello", true), diff(3, "hello", true), reply(2)]) events.send(JSON.stringify(event));
    await view.locator(".repeat-disclosure > summary").filter({ hasText: "3 matching requests" }).waitFor();
    await view.locator(".group-reply").filter({ hasText: "A readable reply" }).waitFor();
    check(await view.locator("#flow-events > li").count() === 1, "repeats must collapse to one row");
    check(!(await view.locator(".repeat-disclosure").evaluate(e => e.open)), "repeat group should start collapsed");
    check(await view.locator(".repeat-group > .comparison-group .comparison-group-key").innerText() === "unknown", "collapsed repeat groups must expose their grouping key");
    await view.locator(".repeat-disclosure > summary").click();
    check(await view.locator(".flow-event").count() === 3, "all individual requests must remain inspectable");
    const visible = await view.locator(".flow-events").innerText();
    check(!visible.includes("SIGNATURE_FIXTURE"), "signature should not dominate readable reply");
    check(!visible.includes("awaiting completed capture"), "missing capture is not a pending lifecycle");
    // A different lineage must never be folded into the repeat group.
    events.send(JSON.stringify(diff(4, "hello", true, "another-lineage")));
    await view.waitForFunction(() => document.querySelectorAll("#flow-events > li").length === 2);
    check(await view.locator("#flow-events > .flow-event .comparison-group-key").innerText() === "another-lineage", "distinct grouping keys must remain distinguishable");
    const changed = diff(5, "<img src=x onerror=alert(1)> literal text");
    changed.counts = { added: 0, removed: 0, transformed: 1, retained: 0 };
    changed.changes = [{ change: "transformed", before: block("Before fixture"), after: block("<img src=x onerror=alert(1)> literal text") }];
    events.send(JSON.stringify(changed));
    await view.locator("#flow-count").filter({ hasText: "5 requests" }).waitFor();
    await inspectLatest();
    await view.locator(".after .readable-text").filter({ hasText: "literal text" }).waitFor();
    check(await view.locator(".before .readable-text").innerText() === "Before fixture", "before text must render directly");
    check(await view.locator(".request-view img").count() === 0, "captured text must never execute as markup");
    await closeEvidence();
    for (let i = 6; i <= 12; i++) events.send(JSON.stringify(diff(i, `Unique fixture ${i}`)));
    await view.waitForFunction(() => document.querySelector("#flow-count").textContent === "12 requests");
    await view.locator("#flow-events").evaluate(e => { e.scrollTop = 100; });
    const before = await view.locator("#flow-events").evaluate(e => e.scrollTop);
    events.send(JSON.stringify(diff(13, "New traffic")));
    await view.locator("#new-activity").waitFor({ state: "visible" });
    check(await view.locator("#flow-events").evaluate(e => e.scrollTop) === before, "new traffic must preserve scroll position");
    await view.locator("#new-activity").click();
    check(await view.locator("#flow-events").evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop < 2), "jump must reach latest content");
    events.send(JSON.stringify(reply(13)));
    await view.locator(".flow-event").last().locator(".model-response").waitFor();
    check(await view.locator("#flow-events").evaluate(e => e.scrollHeight - e.clientHeight - e.scrollTop < 2), "follow mode must follow response growth");
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "narrow layout must not overflow horizontally");
    await view.locator("#clear-history").click();
    check(await view.locator("#flow-count").innerText() === "0 requests", "clear should reset visible count");
    events.send(JSON.stringify(diff(14, "New traffic", true)));
    await view.waitForFunction(() => document.querySelector("#flow-count").textContent === "1 request");
    check(await view.locator("#flow-events > .flow-event").count() === 1, "clear must discard grouping state");
    const metadataChange = (number, oldFields, newFields, afterText = "Same text") => {
      const event = diff(number, afterText);
      const oldBlock = block("Same text"), newBlock = block(afterText);
      Object.assign(oldBlock.value, oldFields); Object.assign(newBlock.value, newFields);
      event.counts = { added: 0, removed: 0, transformed: 1, retained: 0 };
      event.changes = [{ change: "transformed", before: oldBlock, after: newBlock }];
      return event;
    };
    for (const event of [
      metadataChange(15, { cache_control: { type: "ephemeral" } }, {}),
      metadataChange(16, {}, { cache_control: { type: "ephemeral" } }),
      metadataChange(17, { cache_control: { type: "ephemeral", ttl: "5m" } }, { cache_control: { type: "ephemeral", ttl: "1h" } }),
    ]) {
      events.send(JSON.stringify(event));
      await view.waitForFunction(n => document.querySelectorAll("#flow-events .inspect-request").length === n, event.sequence / 100 - 13);
      await inspectLatest();
      const action = {1500: "removed", 1600: "added", 1700: "changed"}[event.sequence];
      await view.locator(".change-explanation").filter({ hasText: `Text unchanged · cache-control metadata ${action}` }).waitFor();
      check(await view.locator(".change-transformed .before, .change-transformed .after").count() === 0, "metadata-only changes must not duplicate text");
      check((await view.locator(".field-changes").innerText()).includes("ephemeral"), "field values must be visible");
      await closeEvidence();
    }
    events.send(JSON.stringify(metadataChange(18, { cache_control: { type: "ephemeral" } }, {}, "Changed text")));
    await view.waitForFunction(() => document.querySelectorAll("#flow-events .inspect-request").length === 5);
    await inspectLatest();
    await view.locator(".change-explanation").filter({ hasText: "Text changed · cache-control metadata removed" }).waitFor();
    check(await view.locator(".flow-event").last().locator(".after .readable-text").innerText() === "Changed text", "mixed change must preserve text diff");
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "field table must fit narrow viewport");
    await closeEvidence();
    events.send(JSON.stringify(diff(19, "Before connection interruption")));
    const usage = { kind: "context.usage", flow_id: "fixture-19", sequence: 1901,
      stream_identity: { stream_id: "unknown", confidence: "none" },
      used_input_tokens: 123, components: { input_tokens: 123, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 },
      context_window_tokens: 200000, context_window_source: "fixture", percent: 0.0615, usage_source: "fixture" };
    events.send(JSON.stringify(usage));
    await view.locator("#context-meter-value").filter({ hasText: "123 /" }).waitFor();
    const countBeforeDisconnect = Number.parseInt(await view.locator("#flow-count").innerText());
    replay = [usage, reply(19), diff(20, "After connection interruption")];
    events.close({ code: 1011, reason: "simulated disconnect between usage and response" });
    await view.locator("#capture-status").filter({ hasText: "retrying" }).waitFor();
    await view.waitForFunction(expected => Number.parseInt(document.querySelector("#flow-count").textContent) === expected, countBeforeDisconnect + 1);
    check(connectionUrls.length === 2 && connectionUrls[1].endsWith("after_sequence=1900"), "reconnect must replay the last sequence boundary");
    check(await view.locator(".flow-event").filter({ hasText: "Request 6" }).locator(".model-response").count() === 1, "same-sequence response must survive replay");
    check(await view.locator("#capture-status").innerText() === "Context: connected", "capture status must recover independently");
    replay = [diff(20, "After connection interruption"), diff(21, "Recovered incomplete capture")];
    events.send(JSON.stringify({ type: "stream-error", message: "simulated partial write" }));
    await view.waitForFunction(expected => Number.parseInt(document.querySelector("#flow-count").textContent) === expected, countBeforeDisconnect + 2);
    check(connectionUrls.length === 3, "capture record errors must trigger replay without refresh");
    // Request 83 regression: cache hints alone must not paint identical tools red/green.
    let number = 22;
    const call = { type: "tool_use", id: "tool-fixture", name: "Bash", input: { command: "pwd", timeout: 1000 } };
    const result = { type: "tool_result", tool_use_id: "tool-fixture", content: "fixture output" };
    for (const [oldValue, newValue, unchanged, label, action] of [
      [call, { ...call, cache_control: { type: "ephemeral" } }, true, "Tool call", "added"],
      [{ ...call, cache_control: { type: "ephemeral" } }, call, true, "Tool call", "removed"],
      [{ ...call, cache_control: { type: "ephemeral", ttl: "5m" } }, { ...call, input: { timeout: 1000, command: "pwd" }, cache_control: { type: "ephemeral", ttl: "1h" } }, true, "Tool call", "changed"],
      [result, { ...result, cache_control: { type: "ephemeral" } }, true, "Tool result", "added"],
      [call, { ...call, input: { command: "ls" }, cache_control: { type: "ephemeral" } }, false],
      [call, { ...call, id: "different-id", cache_control: { type: "ephemeral" } }, false],
    ]) {
      const count = await view.locator("#flow-events .inspect-request").count();
      const event = diff(number++, "tool fixture");
      event.counts = { added: 0, removed: 0, transformed: 1, retained: 0 };
      event.changes = [{ change: "transformed", before: { ...block(""), value: oldValue }, after: { ...block(""), value: newValue } }];
      events.send(JSON.stringify(event));
      await view.waitForFunction(n => document.querySelectorAll("#flow-events .inspect-request").length === n, count + 1);
      await inspectLatest();
      if (unchanged) {
        await view.locator(".request-view .change-explanation").filter({ hasText: `${label} unchanged · cache-control metadata ${action}` }).waitFor();
        check(await view.locator(".request-view .before, .request-view .after").count() === 0, "unchanged tools must not have red/green panels");
        check(await view.locator(".request-view .unchanged-tool").count() === 1, "unchanged tool content appears once");
        await view.locator(".unchanged-tool > summary").click();
        check((await view.locator(".unchanged-tool").innerText()).includes(label === "Tool call" ? "pwd" : "fixture output"), "neutral disclosure preserves readable tool content");
        check((await view.locator(".field-changes").innerText()).includes("ephemeral"), "exact cache metadata stays visible");
      } else {
        await view.locator(".request-view .before").waitFor();
        check(await view.locator(".request-view .after").count() === 1, "real tool changes keep before/after");
        check(await view.locator(".request-view .unchanged-tool").count() === 0, "changed input or ID must not be labeled unchanged");
      }
      await closeEvidence();
    }
    return { grouping: true, individualEvidence: true, visibleReplies: true, safeContent: true, beforeAfter: true, scrollPreserved: true, followLatest: true, narrowLayout: true, clearResetsGroups: true, metadataAddedRemovedModified: true, mixedTextAndMetadata: true, automaticReconnect: true, sameSequenceReplay: true };
  } finally { await context.close(); }
}
