// Generate the fixture first: .venv/bin/python -m src.tests.codex_browser_fixture > src/web/dist/codex-fixture.json
async (page) => {
  const fixture = await (await page.request.get("http://127.0.0.1:8877/codex-fixture.json")).json();
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const errors = [];
  try {
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: { session_id: "fixture", pid: 1, alive: true, harness: "codex", auth_mode: "oauth", selected_model: "synthetic-model" } }));
    await context.route("**/api/sessions/fixture/context-history?*", route => route.fulfill({ json: fixture }));
    await context.routeWebSocket("**/api/sessions/fixture/terminal", ws => ws.send(JSON.stringify({ type: "fixture" })));
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => ws.send(JSON.stringify({ type: "context-batch", events: [], cursor: fixture.cursor })));
    const view = await context.newPage();
    view.on("pageerror", error => errors.push(String(error)));
    await view.goto("http://127.0.0.1:8877");
    await view.locator("#flow-count").filter({ hasText: "2 requests" }).waitFor();
    check((await view.locator("#status").textContent()).includes("Codex connected · OAuth · synthetic-model"), "launch metadata label");
    for (const selector of ["#nav-memory", "#mcp-count-form", "#skill-count-form"])
      check(await view.locator(selector).isHidden(), `unsupported Codex control hidden: ${selector}`);
    const meter = await view.locator("#context-meter-value").textContent();
    check(meter.includes("120 input tokens") && meter.includes("context limit unknown"), "no invented context window");
    const detail = await view.locator("#context-meter-detail").textContent();
    check(detail.includes("cached subset 80") && detail.includes("reasoning subset 10"), "cached/reasoning subsets visible");
    check(await view.locator(".context-visibility").count() === 2, "wire-only provenance on each request");
    check(await view.locator(".context-visibility").filter({ hasText: "observed predecessor" }).count() === 1, "captured previous response lineage");
    await view.locator(".context-diff").filter({ hasText: "No captured continuation reference" }).locator(".inspect-request").click();
    check((await view.locator("body").textContent()).includes("Synthetic instructions"), "request evidence visible");
    const responseButton = view.locator(".inspect-response").first();
    await view.locator("#live-tab").click();
    await responseButton.click();
    await view.locator(".response-payload-host").waitFor({ timeout: 3000 });
    check((await view.locator("body").textContent()).includes("Synthetic Codex reply"), "readable completed response");
    check(errors.length === 0, errors.join("\n"));
    await view.reload();
    await view.locator("#flow-count").filter({ hasText: "2 requests" }).waitFor();
    check((await view.locator("#context-meter-value").textContent()).includes("120 input tokens"), "usage survives replay");
    return { codexLabel: true, requestFields: true, continuation: true, usageSubsets: true, unknownWindow: true, responseEvidence: true, replay: true, realSessions: false };
  } catch (error) { throw new Error(String(error) + "\n" + await context.pages().at(-1).locator("body").innerText()); } finally { await context.close(); }
}
