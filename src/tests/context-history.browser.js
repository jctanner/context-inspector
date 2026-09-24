// Synthetic usage only; no live sessions or model calls.
async (page) => {
  const context = await page.context().browser().newContext({viewport: {width: 1280, height: 900}});
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let live, cleared = false;
  const sample = (n, percent) => ({kind: 'context.usage', flow_id: `flow-${n}`, sequence: n, cursor: n, occurred_at: `2026-09-24T12:00:0${n}Z`, percent,
    used_input_tokens: percent === null ? null : percent * 10, context_window_tokens: 1000, components: {}, usage_source: 'fixture', context_window_source: 'fixture'});
  try {
    await context.route('http://127.0.0.1:8765/**', route => {
      const path = route.request().url().split('127.0.0.1:8765')[1].split('?')[0];
      return route.fulfill({path: '/home/jtanner/workspace/github/jctanner.redhat/context-inspector/src/web/dist' + (path === '/' ? '/index.html' : path)});
    });
    await context.route('**/api/**', route => route.fulfill({status: 404, json: {detail: 'Not Found'}}));
    await context.route('**/api/sessions/active', route => route.fulfill({json: {session_id: 'fixture', alive: true, harness: 'codex', auth_mode: 'oauth'}}));
    await context.route('**/context-history?*', route => route.fulfill({json: {events: cleared ? [] : [sample(1, 20), sample(2, null), sample(3, 60)], total: 0, next_before: null, cursor: 3}}));
    await context.routeWebSocket('**/terminal', ws => {});
    await context.routeWebSocket('**/contexts?*', ws => { live = ws; });
    const view = await context.newPage();
    await view.goto('http://127.0.0.1:8765/');
    await view.locator('.context-chart-point').first().waitFor();
    check(await view.locator('.context-chart-point').count() === 2, 'unknown omitted');
    check(await view.locator('.context-chart-line').count() === 2, 'unknown splits line');
    live.send(JSON.stringify({type: 'context-batch', events: [sample(3, 60), sample(4, 30)], cursor: 4, total: 0}));
    await view.waitForFunction(() => document.querySelectorAll('.context-chart-point').length === 3, null, {timeout: 5000});
    await view.locator('.context-chart-point').last().focus();
    check((await view.locator('#context-history-note').textContent()).includes('30.0%'), 'keyboard details');
    check((await view.locator('#context-meter-value').textContent()).includes('30.0%'), 'meter matches');
    await view.screenshot({path: '/tmp/ci-context-history.png'});
    await view.reload();
    await view.locator('.context-chart-point').first().waitFor();
    check(await view.locator('.context-chart-point').count() === 2, 'replay rebuilds');
    await view.setViewportSize({width: 390, height: 844});
    check(await view.locator('#context-history-chart').evaluate(el => el.scrollWidth <= el.clientWidth), 'responsive graph');
    cleared = true;
    // Usage-only fixture has no request cards to enable the real clear button.
    await view.locator('#clear-history').evaluate(el => { el.disabled = false; });
    await view.locator('#clear-history').click();
    check(await view.locator('.context-chart-point').count() === 0, 'clear resets graph');
    return {passed: true, gaps: true, replay: true, deduplication: true, live: true, keyboard: true};
  } finally { await context.close(); }
}
