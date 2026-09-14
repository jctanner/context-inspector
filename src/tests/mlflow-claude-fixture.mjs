// Isolated real-CLI fixture: dummy credentials, local model, no host user state.
import { createServer } from 'node:http';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const home = mkdtempSync(join(tmpdir(), 'mlflow-claude-smoke-'));
const cwd = join(home, 'workspace');
mkdirSync(cwd);
writeFileSync(join(cwd, 'note.txt'), 'fixture tool result\n');
writeFileSync(join(home, '.claude.json'), JSON.stringify({ hasCompletedOnboarding: true }));
let calls = 0;
const server = createServer(async (request, response) => {
  let body = '';
  for await (const chunk of request) body += chunk;
  if (request.url.includes('count_tokens')) {
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ input_tokens: 20 }));
    return;
  }
  if (!request.url.includes('/messages')) {
    response.setHeader('content-type', 'application/json');
    response.end('{}');
    return;
  }
  calls++;
  const payload = JSON.parse(body);
  const hasResult = payload.messages?.some(message => Array.isArray(message.content)
    && message.content.some(block => block.type === 'tool_result'));
  const content = hasResult
    ? { type: 'text', text: 'Fixture complete.' }
    : { type: 'tool_use', id: 'toolu_fixture_read', name: 'Read', input: { file_path: join(cwd, 'note.txt') } };
  const message = { id: `msg_fixture_${calls}`, type: 'message', role: 'assistant',
    model: 'claude-haiku-4-5-20251001', content: [content],
    stop_reason: hasResult ? 'end_turn' : 'tool_use', stop_sequence: null,
    usage: { input_tokens: 20, output_tokens: 5, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 } };
  if (!payload.stream) {
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify(message));
    return;
  }
  response.setHeader('content-type', 'text/event-stream');
  const event = data => response.write(`event: ${data.type}\ndata: ${JSON.stringify(data)}\n\n`);
  event({ type: 'message_start', message: { ...message, content: [], stop_reason: null } });
  event({ type: 'content_block_start', index: 0, content_block: hasResult
    ? { type: 'text', text: '' } : { ...content, input: {} } });
  event({ type: 'content_block_delta', index: 0, delta: hasResult
    ? { type: 'text_delta', text: content.text }
    : { type: 'input_json_delta', partial_json: JSON.stringify(content.input) } });
  event({ type: 'content_block_stop', index: 0 });
  event({ type: 'message_delta', delta: { stop_reason: message.stop_reason, stop_sequence: null }, usage: message.usage });
  event({ type: 'message_stop' });
  response.end();
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
try {
  const child = spawn('claude', ['--print', '--dangerously-skip-permissions',
    '--model', 'claude-haiku-4-5', '--output-format', 'json',
    '--plugin-dir', '/opt/context-inspector/mlflow-plugin',
    'Read note.txt, then reply Fixture complete.'], {
    cwd,
    env: { ...process.env, HOME: home, CLAUDE_CODE_USE_VERTEX: '0',
      CLAUDE_CODE_USE_BEDROCK: '0', ANTHROPIC_API_KEY: 'fixture-not-a-secret',
      ANTHROPIC_BASE_URL: `http://127.0.0.1:${server.address().port}`,
      CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1', DISABLE_AUTOUPDATER: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stdout = '', stderr = '';
  child.stdout.on('data', data => stdout += data);
  child.stderr.on('data', data => stderr += data);
  const timer = setTimeout(() => child.kill('SIGKILL'), 60000);
  const code = await new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', resolve);
  });
  clearTimeout(timer);
  if (code !== 0) throw new Error(`Fixture CLI failed (${code}): ${stderr}\n${stdout}`);
  const result = JSON.parse(stdout);
  if (result.is_error || !result.result?.includes('Fixture complete.') || calls < 2)
    throw new Error(`Unexpected fixture result: ${stdout}`);
  if (stderr.includes('[mlflow]') || stderr.includes('hook failed')) throw new Error(stderr);
  // Separately exercise upstream subagent-file reconstruction with an explicit
  // synthetic transcript. This is not presented as a real Agent-tool execution.
  const nestedPath = join(home, 'nested.jsonl');
  mkdirSync(join(home, 'nested', 'subagents'), { recursive: true });
  const entry = (type, seconds, content, extra = {}) => ({ type,
    timestamp: `2026-09-14T12:00:0${seconds}.000Z`,
    message: { role: type, model: 'claude-haiku-4-5-20251001', content }, ...extra });
  const nested = [
    entry('user', 0, 'Synthetic nested fixture'),
    entry('assistant', 1, [{ type: 'tool_use', id: 'toolu_fixture_task', name: 'Task',
      input: { subagent_type: 'general-purpose', description: 'fixture child', prompt: 'fixture child prompt' } }]),
    entry('user', 3, [{ type: 'tool_result', tool_use_id: 'toolu_fixture_task', content: 'fixture child done' }],
      { toolUseResult: { agentId: 'child' } }),
    entry('assistant', 4, [{ type: 'text', text: 'Synthetic parent done.' }]),
  ];
  writeFileSync(nestedPath, nested.map(row => JSON.stringify(row)).join('\n') + '\n');
  writeFileSync(join(home, 'nested', 'subagents', 'agent-child.jsonl'),
    [entry('user', 1, 'fixture child prompt'),
      entry('assistant', 2, [{ type: 'text', text: 'Synthetic child response.' }])]
      .map(row => JSON.stringify(row)).join('\n') + '\n');
  const hook = spawn('bash', ['/opt/context-inspector/mlflow-plugin/stop.sh'], {
    cwd, env: { ...process.env, HOME: home }, stdio: ['pipe', 'pipe', 'pipe'],
  });
  let hookErrors = '';
  hook.stderr.on('data', data => hookErrors += data);
  hook.stdin.end(JSON.stringify({ session_id: 'synthetic-nested-session', transcript_path: nestedPath }));
  const hookCode = await new Promise((resolve, reject) => {
    hook.on('error', reject);
    hook.on('close', resolve);
  });
  if (hookCode !== 0 || hookErrors) throw new Error(`Synthetic hook failed: ${hookErrors}`);
  console.log(JSON.stringify({ session_id: result.session_id, calls, result: result.result }));
} finally {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
