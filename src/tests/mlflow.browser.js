// Synthetic traces only; never contacts the running MLflow service.
async (page) => {
  const context = await page.context().browser().newContext({viewport: {width: 1280, height: 900}});
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  let mode = 'ready', calls = 0, filter = '';
  const summary = id => ({trace_id: id, state: 'OK', request_time: '2026-09-24T12:00:00Z', duration: '0.5s',
    request_preview: '<img src=x onerror=alert(1)> fixture question', response_preview: 'fixture answer',
    session_id: 'native-fixture', turn_id: 'turn-1', inspector_session_id: 'inspector-fixture',
    evidence: 'transcript reconstruction', usage: {input_tokens: 20}, metadata: {'codex.turn_id': 'turn-1'}});
  try {
    await context.route('http://127.0.0.1:8765/**', route => {
      const path = route.request().url().split('127.0.0.1:8765')[1].split('?')[0];
      return route.fulfill({path: '/home/jtanner/workspace/github/jctanner.redhat/context-inspector/src/web/dist' + (path === '/' ? '/index.html' : path)});
    });
    await context.route('**/api/**', route => route.fulfill({status: 404, json: {detail: 'Not Found'}}));
    await context.route('**/api/sessions/active', route => route.fulfill({json: null}));
    await context.route('**/api/mlflow/**', route => {
      calls++;
      const url = route.request().url();
      check(url.startsWith('http://127.0.0.1:8765/'), 'same-origin backend only');
      const path = url.split('127.0.0.1:8765')[1].split('?')[0];
      const params = Object.fromEntries((url.split('?')[1] ?? '').split('&').filter(Boolean).map(pair => pair.split('=').map(decodeURIComponent)));
      check(route.request().method() === 'GET', 'read-only viewer');
      if (path.endsWith('/status')) return route.fulfill({json: {available: mode !== 'disabled', message: mode === 'disabled' ? 'MLflow is disabled for this stack.' : 'Current stack run', experiment_name: 'Fixture experiment'}});
      if (mode === 'error') return route.fulfill({status: 503, json: {detail: 'MLflow is unavailable.'}});
      if (path === '/api/mlflow/traces') {
        filter = params.session_id;
        return route.fulfill({json: {traces: mode === 'empty' ? [] : [summary(('page_token' in params) ? 'tr-older' : 'tr-fixture')], next_page_token: mode === 'empty' || ('page_token' in params) ? '' : 'older-page'}});
      }
      return route.fulfill({json: {trace: summary('tr-fixture'), source: 'MLflow trace artifact',
        raw: '{"timestamp": 1760000000000000001}', spans: [
          {id: 'root', parent_id: null, name: 'turn', type: 'AGENT', start_ns: '1760000000000000001', end_ns: '1760000000003500001', inputs: 'question', outputs: 'answer', usage: null, status: {status_code: 'OK'}, attributes: {}},
          {id: 'tool', parent_id: 'root', name: '<script>tool</script>', type: 'TOOL', start_ns: '1760000000000000001', end_ns: '1760000000003500001', inputs: {cmd: 'fixture'}, outputs: 'fixture result', usage: null, status: {status_code: 'OK'}, attributes: {}}
        ]}});
    });
    const view = await context.newPage(); await view.goto('http://127.0.0.1:8765');
    await view.clock.install();
    check(calls === 0, 'no trace fetch before opening tab');
    await view.locator('#nav-mlflow').click();
    await view.locator('#mlflow-list button').first().waitFor();
    check(await view.locator('#session-section').isHidden(), 'session hidden');
    await view.locator('#nav-session').click();
    const hiddenCalls = calls;
    await view.clock.fastForward(11000);
    check(calls === hiddenCalls, 'hidden tab does not poll');
    await view.locator('#nav-mlflow').click();
    await view.waitForFunction(() => !document.querySelector('#mlflow-refresh').disabled);
    const beforePoll = calls;
    await view.clock.fastForward(11000);
    await view.waitForFunction(() => !document.querySelector('#mlflow-refresh').disabled);
    check(calls > beforePoll, 'visible tab polls');
    check(await view.locator('#mlflow-list img').count() === 0, 'untrusted previews rendered as text');
    await view.locator('#mlflow-list button').first().click();
    await view.getByRole('button', {name: 'TOOL · <script>tool</script>', exact: true}).click();
    check((await view.locator('.mlflow-span-detail').innerText()).includes('fixture result'), 'tool output visible');
    check((await view.locator('.mlflow-span-detail').innerText()).includes('3.5 ms'), 'nanosecond duration preserved');
    check(await view.locator('#mlflow-detail script').count() === 0, 'span name is text');
    check(await view.locator('.mlflow-span-row[aria-pressed="true"]').count() === 1, 'selected span highlighted');
    check(await view.locator('.mlflow-timing-track > span').count() === 2, 'recorded timing bars rendered');
    await view.getByRole('tab', {name: 'Inputs & outputs', exact: true}).focus();
    await view.keyboard.press('ArrowRight');
    check(await view.getByRole('tab', {name: 'Attributes', exact: true}).getAttribute('aria-selected') === 'true', 'keyboard span tabs');
    await view.getByRole('tab', {name: 'Inputs & outputs', exact: true}).click();
    await view.getByRole('searchbox', {name: 'Find a span'}).fill('tool');
    check(await view.locator('.mlflow-span-row:visible').count() === 1, 'span search');
    await view.getByRole('searchbox', {name: 'Find a span'}).fill('');
    await view.screenshot({path: '/tmp/ci-mlflow-desktop.png', fullPage: true});
    await view.getByText('MLflow data (JSON)', {exact: true}).click();
    check((await view.locator('#mlflow-detail').innerText()).includes('1760000000000000001'), 'raw JSON precision preserved');
    await view.getByRole('button', {name: 'Show this session', exact: true}).click();
    await view.waitForFunction(() => !document.querySelector('#mlflow-refresh').disabled);
    check(filter === 'native-fixture', 'native session filtering');
    await view.locator('#mlflow-more').click();
    await view.waitForFunction(() => document.querySelectorAll('#mlflow-list li').length === 2);
    check(!await view.locator('#mlflow-auto').isChecked(), 'older pages pause refresh');
    await view.setViewportSize({width: 390, height: 844});
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'mobile no horizontal overflow');
    await view.screenshot({path: '/tmp/ci-mlflow-mobile.png', fullPage: true});
    await view.locator('#nav-workspace').click();
    check(await view.locator('#mlflow-section').isHidden(), 'navigation hides tab');
    mode = 'error'; await view.locator('#nav-mlflow').click();
    await view.waitForFunction(() => document.querySelector('#mlflow-status').textContent.includes('unavailable'));
    mode = 'empty'; await view.locator('#mlflow-refresh').click();
    await view.waitForFunction(() => document.querySelector('#mlflow-status').textContent.includes('No traces'));
    check(await view.locator('#mlflow-list li').count() === 0, 'empty clears list');
    mode = 'disabled'; await view.locator('#mlflow-refresh').click();
    await view.waitForFunction(() => document.querySelector('#mlflow-status').textContent.includes('disabled'));
    check(await view.locator('#mlflow-detail').innerText() === '', 'disabled clears detail');
    return {passed: true, requests: calls};
  } finally { await context.close(); }
}
