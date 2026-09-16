// Synthetic routes only: this test never writes the real workspace configuration.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let count = "10000", revision = "one", writes = 0, failure = false;
  try {
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: null }));
    await context.route("**/api/mcp-dump/count", route => {
      if (route.request().method() === "PUT") {
        writes++;
        const body = route.request().postDataJSON();
        check(route.request().headers()["x-context-inspector"] === "1", "mutation header");
        check(body.revision === revision, "revision must be preserved");
        if (failure) return route.fulfill({ status: 409, json: { detail: "Config changed elsewhere. Refresh and try again." } });
        count = body.tool_count; revision = `revision-${writes}`;
      }
      return route.fulfill({ json: { tool_count: count, revision } });
    });
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    const input = view.locator("#mcp-count");
    const apply = view.locator("#mcp-count-apply");
    const status = view.locator("#mcp-count-status");
    const checkAlignment = async () => {
      const gap = await view.evaluate(() => {
        const nav = document.querySelector(".primary-nav");
        const refresh = document.querySelector("#mcp-count-refresh");
        return nav.getBoundingClientRect().right - parseFloat(getComputedStyle(nav).paddingRight)
          - refresh.getBoundingClientRect().right;
      });
      check(Math.abs(gap) <= 1, `controls must align to right content edge (gap ${gap})`);
      check(await status.evaluate(node => getComputedStyle(node).textAlign) === "right", "status right-aligned");
    };
    await status.filter({ hasText: "Configured: 10000" }).waitFor();
    await checkAlignment();
    for (const invalid of ["0", "-1", "1.5", "foo", ""]) {
      await input.fill(invalid); await apply.click();
      await status.filter({ hasText: "Enter a positive integer" }).waitFor();
    }
    check(writes === 0, "invalid entries must not write");
    await input.fill("100000"); await apply.click();
    await status.filter({ hasText: "Saved 100000 tools. Claude reload is not confirmed." }).waitFor();
    check(count === "100000", "100000 must not be capped");
    await input.fill("12345678901234567890"); await input.press("Enter");
    await status.filter({ hasText: "Saved 12345678901234567890" }).waitFor();
    await checkAlignment();
    check(count === "12345678901234567890", "large integer must remain exact");
    failure = true;
    await input.fill("10"); await apply.click();
    await status.filter({ hasText: "Config changed elsewhere" }).waitFor();
    await view.locator("#mcp-count-refresh").click();
    await status.filter({ hasText: "Configured: 12345678901234567890" }).waitFor();
    check(await input.inputValue() === count, "refresh restores configured count");
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "mobile horizontal fit");
    check(await apply.isVisible(), "mobile Apply visible");
    await checkAlignment();
    return { initialRead: true, positiveOnly: true, noCountCap: true, exactLargeInteger: true,
      saveEvidenceLabel: true, errors: true, refresh: true, mobile: true, realWrites: false };
  } finally { await context.close(); }
}
