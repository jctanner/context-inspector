// Synthetic log responses only. Does not read real traces or start Claude.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let calls = 0;
  try {
    await context.route("http://127.0.0.1:8765/**", route => {
      const path = route.request().url().split("127.0.0.1:8765")[1].split("?")[0];
      return route.fulfill({ path: "/home/jtanner/workspace/github/jctanner.redhat/context-inspector/src/web/dist" + (path === "/" ? "/index.html" : path) });
    });
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: null }));
    await context.route("**/api/strace/search?*", async route => {
      calls++;
      check(route.request().method() === "GET", "read only");
      const q = decodeURIComponent(route.request().url().split("?q=")[1].replace(/\+/g, " "));
      if (q === "fail") return route.fulfill({ status: 429, json: { detail: "A trace search is already running; retry shortly" } });
      return route.fulfill({ json: {
        missing: q === "missing", partial: q === "partial", warnings: q === "partial" ? ["500 match limit reached"] : [],
        files_scanned: 2, bytes_scanned: 123,
        matches: q === "none" || q === "missing" ? [] : [{ path: ".nested/pid.123", line: 31,
          text: 'openat("SKILL.md") <img src=x onerror=alert(1)> & ' + "long ".repeat(1000) }],
      } });
    });
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    await view.locator("#nav-strace").click();
    check(calls === 0, "no automatic sensitive log fetch");
    check(await view.locator("#session-section").isHidden(), "session hidden");
    check(await view.locator("#nav-workspace").innerText() === "/workspace", "renamed workspace");
    const search = async q => {
      await view.locator("#strace-query").fill(q);
      await view.locator("#strace-submit").click();
      await view.waitForFunction(() => !document.querySelector("#strace-submit").disabled);
    };
    await search('openat("SKILL.md") &');
    check((await view.locator("#strace-results").innerText()).includes(".nested/pid.123:31"), "filename and line");
    check(await view.locator("#strace-results img").count() === 0, "plain text, not HTML");
    await view.locator("#nav-session").click();
    check(await view.locator("#strace-section").isHidden(), "trace hidden on session");
    await view.locator("#nav-strace").click();
    check(await view.locator("#strace-results li").count() === 1, "results persist across navigation");
    await search("partial");
    check((await view.locator("#strace-status").innerText()).includes("Results are incomplete"), "partial warning");
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "mobile no page overflow");
    await search("none");
    check(await view.locator("#strace-results li").count() === 0, "empty clears stale results");
    await search("missing");
    check((await view.locator("#strace-status").innerText()).includes("No trace folder"), "missing folder");
    await search("fail");
    check((await view.locator("#strace-status").innerText()).includes("Search failed"), "error surfaced");
    return { passed: true, searches: calls };
  } finally { await context.close(); }
}
