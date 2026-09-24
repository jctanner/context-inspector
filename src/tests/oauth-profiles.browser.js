// Synthetic profile catalog and session lifecycle; no real launches.
async (page) => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  for (const harness of ["claude", "codex"]) {
    const context = await page.context().browser().newContext();
    let active = null;
    const requests = [];
    try {
      await context.route("**/api/**", r => r.fulfill({ status: 404, json: {} }));
      await context.route("**/api/profiles", r => r.fulfill({ json: {
        default: { harness: "claude", auth_mode: "vertex", model: "claude-haiku-4-5" },
        profiles: [
          { harness: "claude", auth_mode: "vertex", available: true, models: ["claude-haiku-4-5"] },
          { harness: "claude", auth_mode: "oauth", available: true, models: ["claude-haiku-4-5", "claude-sonnet-5"] },
          { harness: "codex", auth_mode: "oauth", available: true, models: ["fixture-model-a", "fixture-model-b"] },
        ],
      } }));
      await context.route("**/api/sessions/active", r => r.fulfill({ json: active }));
      await context.route("**/api/sessions", r => {
        const body = r.request().postDataJSON(); requests.push(body);
        active = { session_id: "fixture", pid: 1, alive: true, harness: body.harness, auth_mode: body.auth_mode,
          selected_model: body.model, capabilities: harness === "claude" ? ["context", "usage", "claude_files"] : ["context", "usage"] };
        return r.fulfill({ json: active });
      });
      await context.route("**/api/sessions/fixture/context-history?*", r => r.fulfill({ json: { events: [], cursor: 0, total: 0, next_before: null } }));
      await context.routeWebSocket("**/api/sessions/fixture/terminal", ws => ws.send(JSON.stringify({ type: "fixture" })));
      await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => ws.send(JSON.stringify({ type: "context-batch", events: [], cursor: 0 })));
      const view = await context.newPage();
      await view.goto("http://127.0.0.1:8877");
      await view.locator("#start").click();
      await view.waitForFunction(() => !document.querySelector("#start-model").disabled);
      await view.locator("#start-harness").selectOption(harness);
      await view.locator("#start-auth").selectOption("oauth");
      const model = harness === "claude" ? "claude-sonnet-5" : "fixture-model-b";
      await view.locator("#start-model").selectOption(model);
      check(await view.locator("#start-confirm").isEnabled(), "OAuth profile can launch");
      await view.locator("#start-confirm").click();
      await view.locator("#status").filter({ hasText: "OAuth" }).waitFor();
      check(requests.length === 1 && requests[0].harness === harness && requests[0].auth_mode === "oauth" && requests[0].model === model, "exact profile submitted");
      for (const id of ["#nav-strace", "#mcp-count-form", "#skill-count-form"])
        check(await view.locator(id).isHidden(), `${id} unsupported for OAuth`);
      check(await view.locator("#nav-memory").isVisible() === (harness === "claude"), "Claude file capability");
      await view.reload();
      await view.locator("#status").filter({ hasText: model }).waitFor();
      check(requests.length === 1, "reconnect must not start another CLI");
      check(await view.locator("#nav-strace").isHidden(), "capabilities survive reconnect");
    } finally { await context.close(); }
  }
  return { claudeOAuth: true, codexOAuth: true, nativeCatalogChoice: true, capabilities: true, reconnect: true, realSessions: false };
}
