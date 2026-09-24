// Upstream exporter; input is a private, turn-scoped snapshot prepared by the supervisor.
import { readFileSync } from 'node:fs';
import { ensureInitialized, processNotify } from '@mlflow/codex';
import { tracingContext, getLastActiveTraceId } from '@mlflow/core';

const { payload, metadata } = JSON.parse(readFileSync(process.argv[2], 'utf8'));
if (!ensureInitialized()) throw new Error('MLflow initialization failed');
let failed = false;
const originalError = console.error;
console.error = (...args) => { failed = true; originalError(...args); };
await tracingContext({ metadata }, () => processNotify(payload));

const traceId = getLastActiveTraceId();
if (failed || !traceId) throw new Error('MLflow did not export a trace');
console.log(JSON.stringify({trace_id: traceId, thread_id: payload['thread-id'], turn_id: payload['turn-id']}));
