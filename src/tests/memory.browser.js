// Synthetic read-only responses; never browse real memory contents.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let lists = 0, reads = 0, fail = false;
  const entry = (name, kind = "file", accessible = true, path = name) => ({ name, path, kind, accessible, size: 42, modified_at: 1 });
  const source = "<img src=x onerror=alert(1)>\n# exact source";
  const query = route => Object.fromEntries(route.request().url().split("?")[1].split("&").map(pair => {
    const [key, value = ""] = pair.split("="); return [key, decodeURIComponent(value.replace(/\+/g, " "))];
  }));
  try {
    await context.route("http://127.0.0.1:8765/**", route => {
      const path = route.request().url().split("127.0.0.1:8765")[1].split("?")[0];
      return route.fulfill({ path: "/home/jtanner/workspace/github/jctanner.redhat/context-inspector/src/web/dist" + (path === "/" ? "/index.html" : path) });
    });
    await context.route("**/api/**", route => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await context.route("**/api/sessions/active", route => route.fulfill({ json: null }));
    await context.route("**/api/claude-files?*", route => {
      check(route.request().method() === "GET", "listing read-only"); lists++;
      const params = query(route), path = params.path;
      const entries = path === ".context" ? [entry("config.json", "file", true, ".context/config.json")]
        : path === "empty" ? [] : "after" in params ? [entry("later.txt")]
        : [entry(".context", "directory"), entry("empty", "directory"), entry("note.html"), entry("binary"), entry("link", "symlink", false)];
      return route.fulfill({ json: { path, entries, next_cursor: !path && !("after" in params) ? "1:link" : null } });
    });
    await context.route("**/api/claude-files/file?*", route => {
      check(route.request().method() === "GET", "file read-only"); reads++;
      const path = query(route).path;
      if (path === "binary") return route.fulfill({ status: 415, json: { detail: "Binary file; preview unavailable" } });
      if (fail) return route.fulfill({ status: 404, json: { detail: "Workspace entry no longer exists; refresh" } });
      return route.fulfill({ json: { path, size: 42, modified_at: 1, content: source } });
    });
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    check(lists === 0, "no eager memory scan");
    check(await view.locator("#nav-memory").textContent() === "~/.claude", "renamed tab");
    await view.locator("#nav-memory").click();
    await view.locator("#memory-status").filter({ hasText: "5 entries" }).waitFor();
    check(await view.locator("#session-section").isHidden(), "memory replaces session");
    await view.locator('#memory-files button[data-path="note.html"]').click();
    await view.locator("#memory-file-content").filter({ hasText: "exact source" }).waitFor();
    check(await view.locator("#memory-file-content").innerText() === source, "exact plaintext");
    check(await view.locator("#memory-section img, #memory-section textarea, #memory-section input").count() === 0, "no active content/edit controls");
    check(await view.locator('#memory-files button[data-path="link"]').isDisabled(), "links disabled");
    await view.locator("#memory-more").click();
    await view.locator('#memory-files button[data-path="later.txt"]').waitFor();
    check(await view.locator("#memory-files li").count() === 6, "pagination appends");
    await view.locator('#memory-files button[data-path="binary"]').click();
    await view.locator("#memory-file-meta").filter({ hasText: "Binary file" }).waitFor();
    check(await view.locator("#memory-file-content").innerText() === "", "no stale content after errors");
    await view.locator('#memory-files button[data-path=".context"]').click();
    await view.locator('#memory-files button[data-path=".context/config.json"]').click();
    await view.locator("#memory-file-content").filter({ hasText: "exact source" }).waitFor();
    await view.locator("#nav-workspace").click();
    check(await view.locator("#memory-section").isHidden(), "Memory hides Workspace");
    const before = lists;
    await view.locator("#nav-memory").click();
    check(lists === before, "navigation preserves memory state");
    fail = true;
    await view.locator("#memory-refresh").click();
    await view.locator("#memory-file-meta").filter({ hasText: "no longer exists" }).waitFor();
    check(await view.locator("#memory-file-content").innerText() === "", "refresh clears deleted file");
    await view.locator("#memory-breadcrumbs").getByRole("button", { name: "~/.claude", exact: true }).click();
    await view.locator('#memory-files button[data-path="empty"]').click();
    await view.locator("#memory-status").filter({ hasText: "folder is empty" }).waitFor();
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "mobile fit");
    await view.locator("#nav-session").click();
    check(await view.locator("#memory-section").isHidden(), "Session hides Workspace");
    return { lazy: true, hiddenFiles: true, pagination: true, textSafety: true, errors: true,
      breadcrumbs: true, refresh: true, navigation: true, noActiveSession: true, mobile: true, lists, reads };
  } finally { await context.close(); }
}
