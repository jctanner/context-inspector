// Real container CLI, local Responses fixture, no credentials or host state.
import { createServer } from 'node:http';
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const home = mkdtempSync(join(tmpdir(), 'mlflow-codex-smoke-'));
const state = join(home, '.codex');
const cwd = join(home, 'workspace');
mkdirSync(state); mkdirSync(cwd);
// Existing callback proves chaining without touching host configuration.
const callback = join(home, 'previous.py');
const callbackLog = join(home, 'previous.jsonl');
writeFileSync(callback, `import sys\nwith open(${JSON.stringify(callbackLog)}, 'a') as f: f.write(sys.argv[1]+'\\n')\n`);
writeFileSync(join(state, 'config.toml'), `notify = ["python3", ${JSON.stringify(callback)}]\n[projects.${JSON.stringify(cwd)}]\ntrust_level="trusted"\n`);
let calls = 0;
let phase = 0;
let interruptedRequest;
const requestStarted = new Promise(resolve => interruptedRequest = resolve);
const server = createServer(async (request, response) => {
  for await (const _ of request) { /* drain */ }
  if (!request.url.endsWith('/responses')) { response.end('{}'); return; }
  if (phase === 2) { interruptedRequest(); return; }
  calls++;
  response.setHeader('content-type', 'text/event-stream');
  const event = data => response.write(`event: ${data.type}\ndata: ${JSON.stringify(data)}\n\n`);
  event({ type: 'response.created', response: { id: `resp-${calls}` } });
  if (calls === 1) {
    event({ type: 'response.output_item.done', item: { type: 'function_call', call_id: 'call-fixture',
      name: 'exec_command', namespace: 'functions', arguments: JSON.stringify({cmd: 'printf fixture-tool-result'}) } });
  } else {
    event({ type: 'response.output_item.done', item: {type: 'message', role: 'assistant', id: `msg-${calls}`,
      content: [{type: 'output_text', text: phase === 0 ? 'Fixture first done.' : 'Fixture second done.'}] } });
  }
  event({ type: 'response.completed', response: { id: `resp-${calls}`,
    usage: {input_tokens: 10, output_tokens: 5, total_tokens: 15} } });
  response.end();
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const config = [
  '-c', 'model_provider="fixture"',
  '-c', `model_providers.fixture={name="fixture",base_url="http://127.0.0.1:${server.address().port}/v1",wire_api="responses",supports_websockets=false}`,
  '-c', 'features.enable_request_compression=false',
  '-c', 'model="gpt-6-sol"',
];
async function run(resume, interrupt = false, interactive = false) {
  const args = ['exec', ...(resume ? ['resume', '--last'] : []), '--skip-git-repo-check', '--json',
    '--dangerously-bypass-approvals-and-sandbox', ...config, interrupt ? 'Interrupted fixture' : `Fixture turn ${phase + 1}`];
  const command = interactive ? ['--no-daemon', '--dangerously-bypass-approvals-and-sandbox', ...config, 'Fixture interactive turn'] : args;
  const child = spawn('python3', [...(interactive ? ['/tui-fixture.py', 'python3'] : []), '/opt/context-inspector/codex-mlflow/codex-tracing.py', 'run',
    '/usr/local/bin/codex', ...command], {
    cwd, env: {...process.env, HOME: home, CODEX_HOME: state, NO_PROXY: '*', no_proxy: '*'},
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stdout = '', stderr = '';
  child.stdout.on('data', data => stdout += data);
  child.stderr.on('data', data => stderr += data);
  const timer = setTimeout(() => child.kill('SIGKILL'), 60000);
  if (interrupt) { await requestStarted; child.kill('SIGTERM'); }
  const code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', resolve); });
  clearTimeout(timer);
  if (!interrupt && code !== 0) throw new Error(`CLI failed (${code}): ${stderr}\n${stdout}`);
  if (stderr.includes('export failed')) throw new Error(stderr);
}
try {
  await run(false);
  phase = 1; await run(true);
  await run(false, false, true);
  phase = 2; await run(true, true);
  const log = readFileSync(join(state, 'mlflow-tracing.log'), 'utf8');
  const exports = log.trim().split('\n').map(line => JSON.parse(line));
  const callbacks = readFileSync(callbackLog, 'utf8').trim().split('\n').map(JSON.parse);
  const primary = callbacks.filter(x => ['Fixture turn 1', 'Fixture turn 2', 'Fixture interactive turn'].includes(x['input-messages'].at(-1)));
  if (primary.length !== 3 || callbacks.some(x => x['input-messages'].at(-1) === 'Interrupted fixture'))
    throw new Error('Missing completed fixture turn or unexpected completed interruption');
  if (exports.length !== callbacks.length) throw new Error('Not all native callbacks exported');
  if (callbacks[0]['thread-id'] !== callbacks[1]['thread-id']) throw new Error('Resume lost native thread');
  console.log(JSON.stringify({exports, callbacks, calls, session: callbacks[0]['thread-id'], turns: primary.map(x => x['turn-id'])}));
} finally { server.closeAllConnections(); server.close(); }
