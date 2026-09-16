// Mocked session creation: no containers or real Claude sessions are started.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const models = [], expected = ["claude-haiku-4-5", "claude-sonnet-5", "claude-sonnet-4-6", "claude-opus-4-6"];
  let fail = false, terminal, release = null;
  let activeMetadata = null;
  try {
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: activeMetadata }));
    await context.route("**/api/sessions", async route => {
      models.push(route.request().postDataJSON().model);
      if (fail) return route.fulfill({ status: 500, json: { detail: "fixture start failed" } });
      await new Promise(resolve => { release = resolve; });
      return route.fulfill({ json: { session_id: "fixture", pid: 1, selected_model: route.request().postDataJSON().model } });
    });
    await context.route("**/api/sessions/fixture/context-history?*", route => route.fulfill({ json: { events: [], cursor: 0, total: 0, next_before: null } }));
    await context.routeWebSocket("**/api/sessions/fixture/terminal", ws => { terminal = ws; ws.send("fixture"); });
    await context.routeWebSocket("**/api/sessions/fixture/contexts?*", ws => ws.send(JSON.stringify({ type: "context-batch", events: [], cursor: 0 })));
    const view = await context.newPage(); await view.goto("http://127.0.0.1:8765");
    await view.locator("#status").filter({ hasText: "No active session" }).waitFor();
    const dialog = view.locator("#start-dialog"), select = view.locator("#start-model"), confirm = view.locator("#start-confirm");
    await view.locator("#start").click();
    check(await dialog.isVisible(), "start opens modal");
    check(await select.inputValue() === expected[0], "Haiku default");
    check(JSON.stringify(await select.locator("option").evaluateAll(nodes => nodes.map(n => n.value))) === JSON.stringify(expected), "exact model choices");
    check(await select.evaluate(node => document.activeElement === node), "initial focus");
    await view.keyboard.press("Escape"); check(await dialog.isHidden(), "Escape cancels");
    await view.locator("#start").click(); await view.locator("#start-cancel").click();
    check(models.length === 0, "cancel never creates session");
    fail = true;
    await view.locator("#start").click(); await select.selectOption(expected[1]); await confirm.click();
    await view.locator("#start-dialog-status").filter({ hasText: "fixture start failed" }).waitFor();
    check(await dialog.isVisible() && await confirm.isEnabled(), "errors allow retry");
    fail = false;
    for (const model of expected) {
      if (await dialog.isHidden()) await view.locator("#start").click();
      await select.selectOption(model); await confirm.click();
      await view.locator("#start-dialog-status").filter({ hasText: "Starting Claude" }).waitFor();
      check(await confirm.isDisabled(), "pending prevents duplicate submission");
      await view.keyboard.press("Escape"); check(await dialog.isVisible(), "pending cannot dismiss");
      while (!release) await new Promise(resolve => setTimeout(resolve, 10));
      release(); release = null;
      await dialog.waitFor({ state: "hidden" });
      await view.locator("#start").filter({ hasText: "Connected" }).waitFor();
      check(await view.locator("#status").textContent() === `Claude connected · ${model}`, "selected model in connected label");
      terminal.send(JSON.stringify({ type: "exit", exit_code: 0 }));
      await view.locator("#start").filter({ hasText: "Start Claude" }).waitFor();
    }
    check(JSON.stringify(models.slice(1)) === JSON.stringify(expected), "all selected models sent exactly");
    await view.setViewportSize({ width: 390, height: 844 }); await view.locator("#start").click();
    check(await select.inputValue() === expected[0], "new modal resets to default");
    const box = await dialog.boundingBox(); check(box.x >= 0 && box.x + box.width <= 390, "mobile dialog fits");
    await view.locator("#start-cancel").click();
    activeMetadata = { session_id: "fixture", pid: 1, alive: true, selected_model: "claude-sonnet-4-6" };
    await view.reload();
    await view.locator("#status").filter({ hasText: "Claude connected · claude-sonnet-4-6" }).waitFor();
    check((await view.locator("#status").getAttribute("title")).includes("session launch"), "launch provenance tooltip");
    terminal.close();
    await view.locator("#start").filter({ hasText: "Reconnect" }).waitFor();
    await view.locator("#start").click();
    await view.locator("#status").filter({ hasText: "Claude connected · claude-sonnet-4-6" }).waitFor();
    check(models.length === expected.length + 1, "refresh/reconnect creates no session");
    activeMetadata = { session_id: "fixture", pid: 1, alive: true };
    await view.reload();
    await view.locator("#start").filter({ hasText: "Connected" }).waitFor();
    check(await view.locator("#status").textContent() === "Claude connected", "legacy server has no guessed model");
    return { choices: true, default: true, cancel: true, focus: true, pending: true, retry: true, mobile: true, modelLabel: true, refresh: true, reconnect: true, legacy: true, realSessions: false };
  } finally { await context.close(); }
}
