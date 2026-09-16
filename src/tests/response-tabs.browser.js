// Synthetic captured responses only; no live input or API mutations.
async (page) => {
  const context = await page.context().browser().newContext({ viewport: { width: 1280, height: 800 } });
  const check = (v, message) => { if (!v) throw new Error(message); };
  const request = n => ({ kind: "context.diff", flow_id: `f${n}`, request_number: n, sequence: n * 10, cursor: n,
    predecessor_flow_id: n === 1 ? null : 'f1', predecessor_basis: 'chronological', predecessor_confidence: 'none',
    stream_identity: { stream_id: 'unknown', confidence: 'none', evidence: [] },
    request_purpose: { classification: 'unclassified', confidence: 'none', evidence: [] },
    comparison_lineage: 'unknown', relationship: n === 1 ? 'initial' : 'retry_or_duplicate', body_digest: 'same',
    counts: { added: n === 1 ? 1 : 0, removed: 0, transformed: 0, retained: n === 1 ? 0 : 1 },
    metrics: { body_bytes: 30, token_count: null }, changes: [], exact_request: { body: { decoded: { value: { text: 'fixture' } } } } });
  const reply = n => ({ kind: 'context.response', flow_id: `f${n}`, sequence: n * 10 + 1, cursor: n,
    detail_url: `/api/sessions/fixture/context-details/f${n}/response`, stream_identity: { stream_id: 'unknown', confidence: 'none' },
    purpose: { classification: 'unclassified', confidence: 'none', evidence: [] },
    response: { model: 'fixture-model', message_id: `message-${n}`, stop_reason: 'tool_use', output_tokens: 20,
      content_blocks: [{ type: 'text', text: `Preview ${n}` }] }, exact_response: {} });
  const sse = n => `event: message_start\r\ndata: ${JSON.stringify({ type: 'message_start', message: { model: 'fixture-model', usage: { input_tokens: n * 100, cache_creation_input_tokens: 20, cache_read_input_tokens: 30 } } })}\r\n\r\n: keepalive\n\nevent: vendor_unknown\ndata: not-json\n\ndata: [DONE]\n\n`;
  const full = n => ({ ...reply(n), detail_url: undefined, response: { ...reply(n).response, content_blocks: [
    { type: 'text', text: `Full response ${n} <img src=x onerror=alert(1)>` },
    { type: 'tool_use', id: `tool-${n}`, name: 'Read', input: { file_path: '/fixture/MEMORY.md' } },
    { type: 'thinking', thinking: 'Fixture thinking', signature: 'fixture-signature' },
  ] }, exact_response: { status_code: 200, headers: { 'request-id': `request-${n}` }, body: { wire: { encoding: 'base64', data: 'Zml4dHVyZQ==' }, decoded: { kind: 'sse', value: sse(n) } } } });
  let fetches = 0, sockets = 0, fail = false, pending, delay = false;
  let markStarted;
  const pendingStarted = new Promise(resolve => { markStarted = resolve; });
  try {
    await context.route('**/api/**', route => route.fulfill({ status: 404, json: {} }));
    await context.route('**/api/sessions/active', route => route.fulfill({ json: { session_id: 'fixture', alive: true } }));
    await context.route('**/api/sessions/fixture/context-history?*', route => route.fulfill({ json: { events: [request(1), reply(1), request(2), reply(2)], total: 2, cursor: 4, next_before: null, latest_usage: null } }));
    await context.route('**/api/sessions/fixture/context-details/*/response', async route => {
      fetches++;
      if (fail) { fail = false; await route.fulfill({ status: 503, json: {} }); return; }
      if (delay) await new Promise(resolve => { pending = resolve; markStarted(); });
      const n = Number(route.request().url().match(/\/f(\d+)\//)[1]);
      await route.fulfill({ json: full(n) }).catch(() => {});
    });
    await context.routeWebSocket('**/api/sessions/fixture/terminal', ws => { sockets++; ws.send('fixture'); });
    await context.routeWebSocket('**/api/sessions/fixture/contexts?*', ws => { sockets++; ws.send(JSON.stringify({ type: 'context-batch', events: [], cursor: 4 })); });
    const view = await context.newPage(); await view.goto('http://127.0.0.1:8765');
    await view.locator('#flow-count').filter({ hasText: '2 of 2' }).waitFor();
    check(fetches === 0, 'initial cards must not fetch full responses');
    check(await view.locator('.repeat-disclosure').evaluate(el => !el.open), 'repeat group should begin collapsed');
    const shortcut = n => view.locator(`.group-reply[data-flow-id="f${n}"] .inspect-response`);
    await shortcut(1).click();
    const panel = view.getByRole('tabpanel', { name: 'Response #1', exact: true });
    await panel.locator('.payload-outline').waitFor();
    check(await panel.locator('.payload-add, .payload-remove').count() === 0, 'full response lines are neutral');
    const table = panel.locator('table.payload-diff');
    check((await table.innerText()).includes('cache_creation_input_tokens'), 'complete token usage available');
    check((await table.innerText()).includes('not-json') && (await table.innerText()).includes('[DONE]') && (await table.innerText()).includes('keepalive'), 'unknown SSE data retained');
    check((await panel.locator('.payload-outline').innerText()).includes('Response events'), 'response-specific root label');
    for (const path of ['/events', '/events/0', '/events/0/data', '/events/0/data/message']) {
      await panel.locator(`.payload-outline-link[data-path="${path}"]`).locator('..').locator('..').evaluate(el => { el.open = true; });
    }
    await panel.locator('.payload-outline-link[data-path="/events/0/data/message/usage"]').click();
    check((await panel.locator('.payload-target').innerText()).includes('usage'), 'usage TOC jumps to data');
    await panel.getByRole('button', { name: 'Readable reply & evidence', exact: true }).click();
    await panel.locator('.readable-text').filter({ hasText: 'Full response 1' }).waitFor();
    check((await panel.boundingBox()).width >= 1200, 'response tab must be full width');
    check(await panel.locator('img').count() === 0, 'response text must not execute markup');
    check((await panel.innerText()).includes('/fixture/MEMORY.md') && (await panel.innerText()).includes('tool-1'), 'tool input and ID should be immediately readable');
    check(await panel.locator('.response-evidence').evaluate(el => !el.open), 'raw evidence starts collapsed');
    await panel.locator('.response-evidence > summary').click();
    await panel.getByText('Exact captured response metadata and wire bytes', { exact: true }).click();
    await panel.locator('.evidence-value').filter({ hasText: 'Zml4dHVyZQ==' }).waitFor();
    check((await panel.innerText()).includes('correlated by exact flow_id'), 'response provenance must remain explicit');
    await view.getByRole('tab', { name: 'Live session', exact: true }).click();
    check(!(await view.locator('#flow-events').innerText()).includes('Full response 1'), 'response loading must not replace the live preview');
    await shortcut(1).click();
    check(fetches === 1 && await view.getByRole('tab', { name: 'Response #1', exact: true }).count() === 1, 'reopen must reuse response tab');
    await view.getByRole('tab', { name: 'Live session', exact: true }).click();
    await view.locator('.repeat-disclosure > summary').click();
    await view.locator('.repeat-requests .inspect-request').first().click();
    await view.getByRole('tab', { name: 'Request #1', exact: true }).waitFor();
    check(await view.getByRole('tab', { name: 'Response #1', exact: true }).count() === 1, 'same request and response must have distinct tabs');
    await view.getByRole('tab', { name: 'Response #1', exact: true }).click();
    await view.locator('#nav-memory').click();
    await view.getByRole('button', { name: 'Session', exact: true }).click();
    check(await panel.isVisible(), 'main navigation must preserve response tab');
    await view.setViewportSize({ width: 390, height: 844 });
    check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'response view must fit mobile');
    await view.setViewportSize({ width: 1280, height: 800 });
    await view.getByRole('button', { name: 'Close Response #1', exact: true }).click();
    check(await view.getByRole('tab', { name: 'Request #1', exact: true }).getAttribute('aria-selected') === 'true', 'closing response selects adjacent request');
    await view.getByRole('tab', { name: 'Live session', exact: true }).click();
    fail = true; await shortcut(2).click();
    await view.getByRole('button', { name: 'Retry', exact: true }).click();
    const second = view.getByRole('tabpanel', { name: 'Response #2', exact: true });
    await second.locator('.payload-outline').waitFor();
    await second.locator('.response-baseline').selectOption('f1');
    await second.locator('.payload-remove').first().waitFor();
    check((await second.locator('.payload-provenance').first().innerText()).includes('No thread relationship inferred'), 'comparison provenance');
    await second.getByRole('button', { name: 'Next change', exact: true }).click();
    check(await second.locator('.payload-outline-link[aria-current]').count() === 1, 'change navigation synchronizes outline');
    await second.getByRole('button', { name: 'Side-by-side', exact: true }).click();
    await second.locator('.payload-split').waitFor();
    check((await second.locator('.payload-split').innerText()).includes('200') && (await second.locator('.payload-split').innerText()).includes('100'), 'split shows both usage values');
    fail = true;
    await second.locator('.response-baseline').selectOption('');
    await second.locator('.payload-outline').waitFor();
    await second.locator('.response-baseline').selectOption('f1');
    await second.locator('.payload-view').filter({ hasText: 'Selected response baseline unavailable' }).waitFor();
    await second.getByRole('button', { name: 'Readable reply & evidence', exact: true }).click();
    await second.getByText('Read', { exact: true }).waitFor();
    await second.getByRole('button', { name: 'Decoded response events', exact: true }).click();
    await second.locator('.payload-remove').first().waitFor();
    await view.getByRole('tab', { name: 'Response #2', exact: true }).press('Delete');
    await view.getByRole('tab', { name: 'Live session', exact: true }).click();
    delay = true; await shortcut(2).click();
    await pendingStarted;
    const cancelled = view.waitForEvent('requestfailed', request => request.url().endsWith('/f2/response'));
    await view.getByRole('button', { name: 'Close Response #2', exact: true }).click();
    await cancelled;
    if (pending) pending();
    check(await view.getByRole('tab', { name: 'Response #2', exact: true }).count() === 0, 'closing pending response must not resurrect its tab');
    check(sockets === 2, 'evidence tabs must not create extra sockets');
    return { payload: true, usageOutline: true, comparison: true, split: true, baselineRetry: true, lazy: true, independentTabs: true, groupedAccess: true, fullWidth: true, toolCalls: true, exactEvidence: true, safeText: true, retry: true, closePending: true, mobile: true };
  } finally { if (pending) pending(); await context.close(); }
}
