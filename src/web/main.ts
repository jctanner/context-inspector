import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./style.css";

const terminalElement = document.querySelector<HTMLDivElement>("#terminal")!;
const startButton = document.querySelector<HTMLButtonElement>("#start")!;
const stopButton = document.querySelector<HTMLButtonElement>("#stop")!;
const statusElement = document.querySelector<HTMLSpanElement>("#status")!;
const sizeElement = document.querySelector<HTMLSpanElement>("#terminal-size")!;
const workspaceElement = document.querySelector<HTMLElement>("#workspace")!;
const dividerElement = document.querySelector<HTMLDivElement>("#pane-divider")!;
const flowCountElement = document.querySelector<HTMLSpanElement>("#flow-count")!;
const flowEmptyElement = document.querySelector<HTMLDivElement>("#flow-empty")!;
const flowEventsElement = document.querySelector<HTMLOListElement>("#flow-events")!;
const contextMeterProgress = document.querySelector<HTMLProgressElement>("#context-meter-progress")!;
const contextMeterValue = document.querySelector<HTMLSpanElement>("#context-meter-value")!;
const contextMeterDetail = document.querySelector<HTMLParagraphElement>("#context-meter-detail")!;
const clearHistoryButton = document.querySelector<HTMLButtonElement>("#clear-history")!;
const SESSION_STORAGE_KEY = "context-inspector.active-session";
const CONTEXT_CURSOR_PREFIX = "context-inspector.context-after.";

const terminal = new Terminal({
  cursorBlink: true,
  convertEol: false,
  fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
  fontSize: 14,
  scrollback: 10_000,
  theme: {
    background: "#111723",
    foreground: "#e9eef7",
    cursor: "#8fb4ff",
    selectionBackground: "#34558a99",
  },
});
const fit = new FitAddon();
terminal.loadAddon(fit);
terminal.open(terminalElement);

let sessionId: string | null = null;
let socket: WebSocket | null = null;
let flowSocket: WebSocket | null = null;
let flowCount = 0;
let visibleRowCount = 0;
let splitPercent = 50;
const responseRows = new Map<string, ResponseRow>();
const usageByFlow = new Map<string, ContextUsage>();
const internalFlows = new Set<string>();
const requestRows = new Map<string, HTMLLIElement>();
let latestRequestFlowId: string | null = null;
let displayedUsageFlowId: string | null = null;
let hasContextMeasurement = false;
let latestContextSequence = 0;

type FlowEvent = {
  sequence: number;
  kind: string;
  flow_id?: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  sanitization: { redacted_fields: string[] };
};

type ContextChange = {
  change: "added" | "removed" | "retained" | "transformed";
  moved?: boolean;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
};

type ContextDiff = {
  kind: "context.diff";
  flow_id: string;
  sequence: number;
  predecessor_flow_id: string | null;
  predecessor_basis: string;
  predecessor_confidence: "none" | "low" | "medium" | "high";
  stream_identity: { stream_id: string; classification: string; confidence: string; evidence: string[] };
  request_purpose: { classification: string; confidence: "none" | "low" | "medium" | "high"; evidence: string[] };
  comparison_lineage: string;
  relationship: "initial" | "chronological" | "retry_or_duplicate" | "compaction_candidate";
  counts: Record<ContextChange["change"], number>;
  metrics: { body_bytes: number; previous_body_bytes: number | null; token_count: number | null; token_count_source: string | null };
  changes: ContextChange[];
  exact_request: Record<string, unknown>;
};

type ContextUsage = {
  kind: "context.usage";
  flow_id: string;
  sequence: number;
  stream_identity: { stream_id: string; confidence: string };
  used_input_tokens: number;
  components: { input_tokens: number; cache_creation_input_tokens: number; cache_read_input_tokens: number };
  context_window_tokens: number;
  context_window_source: string;
  percent: number;
  usage_source: string;
};

type ContextResponse = {
  kind: "context.response";
  flow_id: string;
  sequence: number;
  stream_identity: { stream_id: string; confidence: string };
  response: {
    model: string | null;
    message_id: string | null;
    stop_reason: string | null;
    output_tokens: number | null;
    content_blocks: Array<Record<string, unknown>>;
  };
  purpose: { classification: string; confidence: "none" | "low" | "medium" | "high"; evidence: string[] };
  exact_response: Record<string, unknown>;
};

type ResponseRow = {
  item: HTMLLIElement;
  firstSequence: number;
  blocks: number;
  bytes: number;
};

function setStatus(text: string, state: "idle" | "active" | "error" = "idle"): void {
  statusElement.textContent = text;
  statusElement.dataset.state = state;
}

function sendResize(): void {
  fit.fit();
  sizeElement.textContent = `${terminal.cols} × ${terminal.rows}`;
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "resize", rows: terminal.rows, cols: terminal.cols }));
  }
}

function detachSockets(): void {
  socket = null;
  flowSocket?.close();
  flowSocket = null;
}

function forgetSession(): void {
  detachSockets();
  if (sessionId !== null) localStorage.removeItem(`${CONTEXT_CURSOR_PREFIX}${sessionId}`);
  localStorage.removeItem(SESSION_STORAGE_KEY);
  sessionId = null;
  startButton.disabled = false;
  startButton.textContent = "Start Claude";
  stopButton.disabled = true;
}

function resetContextView(): void {
  flowCount = 0;
  visibleRowCount = 0;
  responseRows.clear();
  usageByFlow.clear();
  internalFlows.clear();
  requestRows.clear();
  latestRequestFlowId = null;
  displayedUsageFlowId = null;
  hasContextMeasurement = false;
  latestContextSequence = 0;
  clearHistoryButton.disabled = true;
  contextMeterProgress.value = 0;
  contextMeterValue.textContent = "Awaiting response usage";
  contextMeterDetail.textContent = "Token accounting arrives in the model response; request bytes are not used as a substitute.";
  flowEventsElement.replaceChildren();
  flowEmptyElement.hidden = false;
  flowCountElement.textContent = "0 requests";
}

function textElement(tag: string, className: string, text: string): HTMLElement {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

function summarize(event: FlowEvent): string {
  if (event.kind === "request.started") {
    const request = event.payload.request as { method?: string; url?: string } | undefined;
    return `${request?.method ?? "HTTP"} ${request?.url ?? "request"}`;
  }
  if (event.kind === "response.started") return `HTTP ${String(event.payload.status_code ?? "response")}`;
  if (event.kind === "response.block") {
    const body = event.payload.body as { wire?: { byte_length?: number } } | undefined;
    return `${String(body?.wire?.byte_length ?? 0)} wire bytes at offset ${String(event.payload.offset ?? 0)}`;
  }
  if (event.kind === "flow.completed") return `${String(event.payload.response_body_bytes ?? 0)} response bytes archived`;
  if (event.kind === "flow.error") return String(event.payload.message ?? "Flow failed");
  return "Live stream is incomplete";
}

function addEvidence(details: HTMLElement, title: string, value: unknown, evidenceClass: string): HTMLDetailsElement {
  const section = document.createElement("details");
  section.className = `evidence ${evidenceClass}`;
  section.append(textElement("summary", "evidence-title", title));
  const output = textElement("pre", "evidence-value", "Expand to materialize this potentially large value.");
  let materialized = false;
  section.addEventListener("toggle", () => {
    if (section.open && !materialized) {
      output.textContent = JSON.stringify(value, null, 2);
      materialized = true;
    }
  });
  section.append(output);
  details.append(section);
  return section;
}

function renderContextDiff(diff: ContextDiff): void {
  flowCount += 1;
  visibleRowCount += 1;
  flowEmptyElement.hidden = true;
  clearHistoryButton.disabled = false;
  latestRequestFlowId = diff.flow_id;
  if (hasContextMeasurement) {
    contextMeterDetail.textContent = `Showing the previous completed measurement while request ${diff.flow_id} awaits response usage · ${diff.metrics.body_bytes.toLocaleString()} exact request bytes.`;
  } else {
    contextMeterValue.textContent = "Awaiting response usage";
    contextMeterDetail.textContent = `Request ${diff.flow_id} · ${diff.metrics.body_bytes.toLocaleString()} exact bytes. Bytes are not converted into tokens.`;
  }
  const item = document.createElement("li");
  item.className = `flow-event context-diff relationship-${diff.relationship}`;
  if (diff.request_purpose.classification.startsWith("likely_internal_")) {
    item.classList.add("purpose-internal");
    item.dataset.purpose = diff.request_purpose.classification;
    internalFlows.add(diff.flow_id);
  }
  const header = document.createElement("header");
  header.append(textElement("span", "event-sequence", `request #${diff.sequence}`));
  header.append(textElement("strong", "event-kind", diff.relationship.replaceAll("_", " ")));
  header.append(textElement("span", "event-time", `${diff.metrics.body_bytes.toLocaleString()} bytes`));
  const countSummary = `+${diff.counts.added} added · −${diff.counts.removed} removed · ~${diff.counts.transformed} changed · =${diff.counts.retained} retained`;
  item.append(header, textElement("p", "event-summary context-counts", countSummary));
  item.append(textElement("p", "context-provenance", "Request only · normalized from the captured API request. Response content is not included in these change blocks."));
  item.append(textElement("p", `request-purpose confidence-${diff.request_purpose.confidence}`, `Request purpose: ${diff.request_purpose.classification.replaceAll("_", " ")} · ${diff.request_purpose.confidence} confidence · lineage ${diff.comparison_lineage} · ${diff.request_purpose.evidence.join(", ")}`));
  item.append(textElement("p", `stream-identity confidence-${diff.stream_identity.confidence}`, `Stream: ${diff.stream_identity.stream_id} · ${diff.stream_identity.confidence} confidence`));
  const harnessBlockCount = diff.changes.flatMap((change) => [change.before, change.after])
    .filter((block) => typeof block?.origin === "string" && block.origin.startsWith("harness_injected_")).length;
  if (harnessBlockCount > 0) {
    item.append(textElement("p", "harness-origin-summary", `${harnessBlockCount} changed-side block observation${harnessBlockCount === 1 ? "" : "s"} classified as harness-injected; expand changes for origin evidence.`));
  }
  const tokens = diff.metrics.token_count === null
    ? "Token count unavailable in request"
    : `${diff.metrics.token_count.toLocaleString()} tokens (${diff.metrics.token_count_source})`;
  item.append(textElement("p", "context-metrics", tokens));
  if (diff.predecessor_flow_id !== null) {
    item.append(textElement("p", "comparison-confidence", `Compared by ${diff.predecessor_basis.replaceAll("_", " ")} · ${diff.predecessor_confidence} confidence · predecessor ${diff.predecessor_flow_id}`));
  }
  for (const changeKind of ["added", "removed", "transformed", "retained"] as const) {
    const changes = diff.changes.filter((change) => change.change === changeKind);
    if (changes.length) addEvidence(item, `${changeKind} request-context blocks (${changes.length})`, changes, `change-${changeKind}`);
  }
  addEvidence(item, "Exact captured request fields", diff.exact_request, "exact");
  const responsePlaceholder = textElement("p", "response-awaiting", "Model response · awaiting completed capture");
  responsePlaceholder.dataset.flowId = diff.flow_id;
  item.append(responsePlaceholder);
  requestRows.set(diff.flow_id, item);
  flowEventsElement.append(item);
  item.scrollIntoView({ block: "nearest" });
  updateCount();
}

function renderContextResponse(response: ContextResponse): void {
  const item = requestRows.get(response.flow_id);
  if (!item) return;
  item.querySelector(".response-awaiting")?.remove();
  item.querySelector(".model-response")?.remove();
  const section = document.createElement("section");
  section.className = "model-response";
  section.append(textElement("h3", "model-response-title", "Correlated model response"));
  section.append(textElement("p", "response-provenance", "Response only · semantic blocks reconstructed from the completed captured SSE stream, correlated by exact flow_id."));
  section.append(textElement("p", `response-purpose confidence-${response.purpose.confidence}`, `Purpose: ${response.purpose.classification.replaceAll("_", " ")} · ${response.purpose.confidence} confidence · ${response.purpose.evidence.join(", ")}`));
  const metadata = [
    response.response.model ?? "unknown model",
    response.response.stop_reason ? `stop: ${response.response.stop_reason}` : "stop reason unavailable",
    response.response.output_tokens === null ? "output tokens unavailable" : `${response.response.output_tokens.toLocaleString()} output tokens`,
  ].join(" · ");
  section.append(textElement("p", "response-metadata", metadata));
  addEvidence(section, `Reconstructed response content blocks (${response.response.content_blocks.length})`, response.response.content_blocks, "interpreted");
  const exactBody = response.exact_response.body as { wire?: unknown; decoded?: unknown; decode_status?: unknown } | undefined;
  const exactWire = { ...response.exact_response, body: { wire: exactBody?.wire } };
  addEvidence(section, "Exact captured response metadata and wire bytes", exactWire, "exact");
  addEvidence(section, "Losslessly decoded response SSE", { decoded: exactBody?.decoded, decode_status: exactBody?.decode_status }, "interpreted");
  item.append(section);
  if (response.purpose.classification.startsWith("likely_internal_")) {
    item.classList.add("purpose-internal");
    item.dataset.purpose = response.purpose.classification;
    internalFlows.add(response.flow_id);
    if (displayedUsageFlowId === response.flow_id) {
      const replacement = [...usageByFlow.values()]
        .filter((usage) => !internalFlows.has(usage.flow_id))
        .sort((left, right) => right.sequence - left.sequence)[0];
      if (replacement) showContextUsage(replacement);
    }
  }
}

function showContextUsage(usage: ContextUsage): void {
  hasContextMeasurement = true;
  displayedUsageFlowId = usage.flow_id;
  contextMeterProgress.value = usage.percent;
  contextMeterValue.textContent = `${usage.used_input_tokens.toLocaleString()} / ${usage.context_window_tokens.toLocaleString()} tokens · ${usage.percent.toFixed(1)}%`;
  contextMeterDetail.textContent = `Latest measured request not classified as internal · flow ${usage.flow_id}. Uncached ${usage.components.input_tokens.toLocaleString()} + cache creation ${usage.components.cache_creation_input_tokens.toLocaleString()} + cache read ${usage.components.cache_read_input_tokens.toLocaleString()}. Usage: ${usage.usage_source}; limit: ${usage.context_window_source}.`;
}

function renderContextUsage(usage: ContextUsage): void {
  usageByFlow.set(usage.flow_id, usage);
  if (internalFlows.has(usage.flow_id)) return;
  const displayed = displayedUsageFlowId === null ? undefined : usageByFlow.get(displayedUsageFlowId);
  if (!displayed || internalFlows.has(displayed.flow_id) || usage.sequence >= displayed.sequence) {
    showContextUsage(usage);
  }
}

function updateCount(): void {
  flowCountElement.textContent = `${flowCount} request${flowCount === 1 ? "" : "s"}`;
}

function createEventRow(event: FlowEvent): HTMLLIElement {
  const item = document.createElement("li");
  item.className = `flow-event kind-${event.kind.replace(".", "-")}`;
  const header = document.createElement("header");
  header.append(textElement("span", "event-sequence", `#${event.sequence}`));
  header.append(textElement("strong", "event-kind", event.kind));
  header.append(textElement("time", "event-time", new Date(event.occurred_at).toLocaleTimeString()));
  item.append(header, textElement("p", "event-summary", summarize(event)));
  visibleRowCount += 1;
  return item;
}

function setEvidence(item: HTMLElement, event: FlowEvent, includeBody: boolean): void {
  item.querySelectorAll(".evidence").forEach((element) => element.remove());
  const payload = event.payload as Record<string, unknown>;
  const request = payload.request as Record<string, unknown> | undefined;
  const body = (request?.body ?? payload.body) as { wire?: unknown; decoded?: unknown; decode_status?: string } | undefined;
  if (includeBody && body?.wire) addEvidence(item, "Latest exact capture-boundary bytes", body.wire, "exact");
  if (includeBody && body?.decoded) addEvidence(item, `Latest interpreted ${String((body.decoded as { kind?: string }).kind ?? "body")}`, body.decoded, "interpreted");
  addEvidence(item, "Event metadata", { flow_id: event.flow_id, payload, sanitization: event.sanitization }, "metadata");
}

function updateResponseRow(event: FlowEvent): boolean {
  if (!event.flow_id || !["response.started", "response.block", "flow.completed"].includes(event.kind)) return false;
  let row = responseRows.get(event.flow_id);
  if (!row) {
    const item = createEventRow(event);
    row = { item, firstSequence: event.sequence, blocks: 0, bytes: 0 };
    responseRows.set(event.flow_id, row);
    flowEventsElement.append(item);
  }
  const kind = row.item.querySelector<HTMLElement>(".event-kind")!;
  const sequence = row.item.querySelector<HTMLElement>(".event-sequence")!;
  const time = row.item.querySelector<HTMLTimeElement>(".event-time")!;
  const summary = row.item.querySelector<HTMLElement>(".event-summary")!;
  sequence.textContent = row.firstSequence === event.sequence ? `#${event.sequence}` : `#${row.firstSequence}–${event.sequence}`;
  time.textContent = new Date(event.occurred_at).toLocaleTimeString();
  row.item.className = `flow-event kind-${event.kind.replace(".", "-")}`;
  if (event.kind === "response.started") {
    kind.textContent = "response stream";
    summary.textContent = summarize(event);
    setEvidence(row.item, event, false);
  } else if (event.kind === "response.block") {
    const body = event.payload.body as { wire?: { byte_length?: number } } | undefined;
    row.blocks += 1;
    row.bytes += Number(body?.wire?.byte_length ?? 0);
    kind.textContent = "response streaming";
    summary.textContent = `${row.blocks} transport chunks · ${row.bytes.toLocaleString()} wire bytes observed`;
    setEvidence(row.item, event, true);
  } else {
    kind.textContent = "response completed";
    summary.textContent = `${String(event.payload.response_blocks ?? row.blocks)} transport chunks collapsed · ${Number(event.payload.response_body_bytes ?? row.bytes).toLocaleString()} response bytes archived`;
    setEvidence(row.item, event, false);
    row.item.scrollIntoView({ block: "nearest" });
  }
  return true;
}

function renderFlowEvent(event: FlowEvent): void {
  flowCount += 1;
  flowEmptyElement.hidden = true;
  if (updateResponseRow(event)) {
    updateCount();
    return;
  }
  const item = createEventRow(event);
  setEvidence(item, event, true);
  flowEventsElement.append(item);
  item.scrollIntoView({ block: "nearest" });
  updateCount();
}

function connectFlowSocket(id: string, scheme: string): void {
  flowSocket?.close();
  const savedCursor = Number.parseInt(localStorage.getItem(`${CONTEXT_CURSOR_PREFIX}${id}`) ?? "0", 10);
  const afterSequence = Number.isSafeInteger(savedCursor) && savedCursor >= 0 ? savedCursor : 0;
  latestContextSequence = afterSequence;
  flowSocket = new WebSocket(`${scheme}://${location.host}/api/sessions/${id}/contexts?after_sequence=${afterSequence}`);
  flowSocket.addEventListener("message", (message) => {
    const event = JSON.parse(String(message.data)) as ContextDiff | ContextUsage | ContextResponse | { type: string; message: string };
    if ("type" in event) {
      setStatus(`Capture stream: ${event.message}`, "error");
      return;
    }
    latestContextSequence = Math.max(latestContextSequence, event.sequence);
    if (event.kind === "context.usage") renderContextUsage(event);
    else if (event.kind === "context.response") renderContextResponse(event);
    else renderContextDiff(event);
  });
  const connectedFlowSocket = flowSocket;
  flowSocket.addEventListener("error", () => {
    if (flowSocket === connectedFlowSocket) setStatus("Capture stream disconnected", "error");
  });
}

function clearContextHistory(): void {
  if (sessionId === null) return;
  localStorage.setItem(`${CONTEXT_CURSOR_PREFIX}${sessionId}`, String(latestContextSequence));
  responseRows.clear();
  requestRows.clear();
  flowCount = 0;
  visibleRowCount = 0;
  flowEventsElement.replaceChildren();
  flowEmptyElement.hidden = false;
  flowCountElement.textContent = "0 requests";
  clearHistoryButton.disabled = true;
}

function connectSession(id: string): void {
  sessionId = id;
  localStorage.setItem(SESSION_STORAGE_KEY, id);
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  connectFlowSocket(id, scheme);
  socket?.close();
  socket = new WebSocket(`${scheme}://${location.host}/api/sessions/${id}/terminal`);
  const connectedSocket = socket;
  socket.binaryType = "arraybuffer";
  socket.addEventListener("open", () => {
    if (socket !== connectedSocket) return;
    startButton.disabled = true;
    startButton.textContent = "Connected";
    stopButton.disabled = false;
    setStatus("Claude connected", "active");
    sendResize();
    terminal.focus();
  });
  socket.addEventListener("message", (event) => {
    if (event.data instanceof ArrayBuffer) {
      terminal.write(new Uint8Array(event.data));
      return;
    }
    const message = JSON.parse(String(event.data)) as { type?: string; exit_code?: number | null; message?: string };
    if (message.type === "exit") {
      setStatus(`Claude exited (${message.exit_code ?? "unknown"})`);
      forgetSession();
    } else if (message.type === "error") {
      setStatus(message.message ?? "Terminal error", "error");
    }
  });
  socket.addEventListener("close", () => {
    if (socket !== connectedSocket) return;
    socket = null;
    if (sessionId === id) {
      setStatus("Browser detached; Claude is still running", "idle");
      startButton.disabled = false;
      startButton.textContent = "Reconnect";
      stopButton.disabled = false;
    }
  });
  socket.addEventListener("error", () => {
    if (socket === connectedSocket) setStatus("Terminal connection error", "error");
  });
}

async function startSession(): Promise<void> {
  startButton.disabled = true;
  terminal.clear();
  setStatus("Starting containers…", "active");
  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ extra_args: [] }),
    });
    if (!response.ok) throw new Error(await response.text());
    const created = await response.json() as { session_id: string };
    resetContextView();
    connectSession(created.session_id);
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Could not start session", "error");
    forgetSession();
  }
}

async function stopSession(): Promise<void> {
  if (sessionId === null) return;
  stopButton.disabled = true;
  setStatus("Stopping…", "active");
  const stopping = sessionId;
  try {
    await fetch(`/api/sessions/${stopping}`, { method: "DELETE" });
  } finally {
    socket?.close();
    forgetSession();
    setStatus("Stopped");
  }
}

async function resumePersistedSession(): Promise<void> {
  const persisted = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!persisted) return;
  setStatus("Checking previous session…", "active");
  try {
    const response = await fetch(`/api/sessions/${persisted}`);
    if (!response.ok) throw new Error("Session is no longer available");
    const status = await response.json() as { alive: boolean };
    if (!status.alive) throw new Error("Previous Claude session has exited");
    resetContextView();
    setStatus("Reconnecting…", "active");
    connectSession(persisted);
  } catch (error) {
    forgetSession();
    setStatus(error instanceof Error ? error.message : "Previous session is unavailable", "idle");
  }
}

terminal.onData((data) => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "input", data }));
  }
});

new ResizeObserver(sendResize).observe(terminalElement);
startButton.addEventListener("click", () => {
  if (sessionId !== null) {
    terminal.clear();
    resetContextView();
    connectSession(sessionId);
  }
  else void startSession();
});
stopButton.addEventListener("click", () => void stopSession());
clearHistoryButton.addEventListener("click", clearContextHistory);
window.addEventListener("beforeunload", () => {
  socket?.close();
  flowSocket?.close();
});

function setSplit(next: number): void {
  splitPercent = Math.max(25, Math.min(75, next));
  workspaceElement.style.setProperty("--terminal-width", `${splitPercent}%`);
  dividerElement.setAttribute("aria-valuenow", String(Math.round(splitPercent)));
  sendResize();
}

dividerElement.addEventListener("pointerdown", (startEvent) => {
  dividerElement.setPointerCapture(startEvent.pointerId);
  const move = (event: PointerEvent) => {
    const bounds = workspaceElement.getBoundingClientRect();
    setSplit(((event.clientX - bounds.left) / bounds.width) * 100);
  };
  dividerElement.addEventListener("pointermove", move);
  dividerElement.addEventListener("pointerup", () => dividerElement.removeEventListener("pointermove", move), { once: true });
});
dividerElement.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  setSplit(splitPercent + (event.key === "ArrowRight" ? 2 : -2));
});
sendResize();
void resumePersistedSession();
