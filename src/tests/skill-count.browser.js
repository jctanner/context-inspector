// All API routes are synthetic; no real skills or session state are mutated.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let count = "3", target = null, running = false, revision = "first", writes = 0, fail = false;
  try {
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: null }));
    await context.route("**/api/mcp-dump/count", route => route.fulfill({ json: { tool_count: "140", revision: "mcp" } }));
    await context.route("**/api/skill-dump/count", route => {
      if (route.request().method() === "PUT") {
        writes++;
        if (fail) return route.fulfill({ status: 409, json: { detail: "Skill files changed elsewhere. Refresh and try again." } });
        const body = route.request().postDataJSON();
        check(body.revision === revision, "revision checked");
        check(route.request().headers()["x-context-inspector"] === "1", "mutation header");
        target = body.skill_count; running = true;
        return route.fulfill({ status: 202, json: { skill_count: count, target_count: target, running, revision, error: null } });
      }
      if (running) { count = target; running = false; revision = `revision-${writes}`; }
      return route.fulfill({ json: { skill_count: count, target_count: target, running, revision, error: null } });
    });
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    const input = view.locator("#skill-count"), apply = view.locator("#skill-count-apply"), status = view.locator("#skill-count-status");
    await status.filter({ hasText: "On disk: 3" }).waitFor();
    check(await input.inputValue() === "3", "current count populated");
    for (const value of ["0", "-1", "1.2", "abc", ""]) {
      await input.fill(value); await apply.click();
      await status.filter({ hasText: "Enter a positive integer" }).waitFor();
    }
    check(writes === 0, "invalid counts do not write");
    await input.fill("100000"); await apply.click();
    await status.filter({ hasText: "Updating: 3 / 100000" }).waitFor();
    check(await apply.isDisabled(), "disable duplicate submissions");
    await status.filter({ hasText: "On disk: 100000" }).waitFor();
    await input.fill("1"); await input.press("Enter");
    await status.filter({ hasText: "On disk: 1" }).waitFor();
    check(await view.locator("#skill-count-warning").isVisible(), "deletion warning visible");
    check(await view.locator("#mcp-count").inputValue() === "140", "MCP control unchanged");
    fail = true;
    await input.fill("5"); await apply.click();
    await status.filter({ hasText: "changed elsewhere" }).waitFor();
    await view.locator("#skill-count-refresh").click();
    await status.filter({ hasText: "On disk: 1" }).waitFor();
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "mobile fit");
    check(await apply.isVisible(), "mobile controls visible");
    return { currentCount: true, positiveInteger: true, progress: true, decrease: true,
      deletionWarning: true, conflict: true, refresh: true, mobile: true, realWrites: false };
  } finally { await context.close(); }
}
