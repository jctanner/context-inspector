import { renderContextHistory } from "./context-history";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WorkspaceView } from "./workspace";
import { MLflowView } from "./mlflow";
import { setupStrace } from "./strace";
import { StartDialog, type LaunchSelection } from "./start-dialog";
import { setupMcpCount } from "./mcp-count";
import { setupSkillCount } from "./skill-count";
import "@xterm/xterm/css/xterm.css";
import "./style.css";
import { disclosure, readableBlock, readableChange, readableValue } from "./readable";
import { FastContext } from "./fast-context";
import { RequestTabs } from "./request-tabs";
import { addPayloadDiff } from "./payload-diff";
import { addResponsePayload, type ResponseChoice } from "./response-payload";

setupMcpCount();
setupSkillCount();
setupStrace();

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
const newActivityButton = document.querySelector<HTMLButtonElement>("#new-activity")!;
const meterStatus = document.querySelector<HTMLElement>("#context-meter-status")!;
const captureStatus = document.querySelector<HTMLElement>("#capture-status")!;
let flowRetryTimer: number | undefined;
let flowGeneration = 0;
let flowRetryCount = 0;
const receivedContextEvents = new Set<string>();
let fastContext: FastContext | null = null;
let compactView = false;
let batchRendering = false;
const olderButton = document.querySelector<HTMLButtonElement>("#older-history")!;
const requestTabs = new RequestTabs(() => requestAnimationFrame(sendResize));
olderButton.addEventListener("click", () => { void fastContext?.older(); });

function closeFlowConnection(): void {
  fastContext?.stop();
  fastContext = null;
  flowGeneration += 1;
  window.clearTimeout(flowRetryTimer);
  flowRetryTimer = undefined;
  const previous = flowSocket;
  flowSocket = null;
  previous?.close();
  captureStatus.textContent = "Context: not connected";
}
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
let selectedSessionModel: string | null = null;
let selectedLaunch: { harness?: string | null; auth_mode?: string | null; capabilities?: string[] } = {};
const memoryView = new WorkspaceView("memory", "/api/claude-files", "~/.claude");
const sessionSection = document.querySelector<HTMLElement>("#session-section")!;
const memorySection = document.querySelector<HTMLElement>("#memory-section")!;
const navSession = document.querySelector<HTMLButtonElement>("#nav-session")!;
const navMemory = document.querySelector<HTMLButtonElement>("#nav-memory")!;
const workspaceView = new WorkspaceView();
const filesSection = document.querySelector<HTMLElement>("#workspace-section")!;
const navWorkspace = document.querySelector<HTMLButtonElement>("#nav-workspace")!;
const traceSection = document.querySelector<HTMLElement>("#strace-section")!;
const navStrace = document.querySelector<HTMLButtonElement>("#nav-strace")!;
const mlflowView = new MLflowView();
const mlflowSection = document.querySelector<HTMLElement>("#mlflow-section")!;
const navMlflow = document.querySelector<HTMLButtonElement>("#nav-mlflow")!;
function hideMlflow(): void {
  mlflowSection.hidden = true; navMlflow.removeAttribute("aria-current"); mlflowView.hide();
}
navMlflow.onclick = () => {
  for (const section of [sessionSection, memorySection, filesSection, traceSection]) section.hidden = true;
  for (const nav of [navSession, navMemory, navWorkspace, navStrace]) nav.removeAttribute("aria-current");
  mlflowSection.hidden = false; navMlflow.setAttribute("aria-current", "page"); mlflowView.show();
};
navSession.onclick = () => {
  hideMlflow();
  traceSection.hidden = true; navStrace.removeAttribute("aria-current");
  filesSection.hidden = true; navWorkspace.removeAttribute("aria-current");
  sessionSection.hidden = false; memorySection.hidden = true;
  navSession.setAttribute("aria-current", "page"); navMemory.removeAttribute("aria-current");
  requestTabs.resume();
};
navMemory.onclick = () => {
  hideMlflow();
  traceSection.hidden = true; navStrace.removeAttribute("aria-current");
  filesSection.hidden = true; navWorkspace.removeAttribute("aria-current");
  sessionSection.hidden = true; memorySection.hidden = false;
  navMemory.setAttribute("aria-current", "page"); navSession.removeAttribute("aria-current");
  memoryView.show();
};
navWorkspace.onclick = () => {
  hideMlflow();
  traceSection.hidden = true; navStrace.removeAttribute("aria-current");
  sessionSection.hidden = true; memorySection.hidden = true; filesSection.hidden = false;
  navSession.removeAttribute("aria-current"); navMemory.removeAttribute("aria-current");
  navWorkspace.setAttribute("aria-current", "page"); workspaceView.show();
};
navStrace.onclick = () => {
  hideMlflow();
  sessionSection.hidden = true; memorySection.hidden = true; filesSection.hidden = true;
  for (const nav of [navSession, navMemory, navWorkspace]) nav.removeAttribute("aria-current");
  traceSection.hidden = false; navStrace.setAttribute("aria-current", "page");
  document.querySelector<HTMLInputElement>("#strace-query")!.focus();
};
function applyLaunchCapabilities(launch: typeof selectedLaunch): void {
  const legacy = ["claude_files", "strace", "mcp_dump", "skill_dump"];
  const fallback = launch.harness === "codex" ? ["strace"] : launch.auth_mode === "oauth" ? ["claude_files", "strace"] : legacy;
  const capabilities = new Set(launch.capabilities ?? fallback);
  for (const [element, capability] of [
    [navMemory, "claude_files"], [navStrace, "strace"],
    [document.querySelector<HTMLElement>("#mcp-count-form")!, "mcp_dump"],
    [document.querySelector<HTMLElement>("#skill-count-form")!, "skill_dump"],
  ] as const) element.hidden = !capabilities.has(capability);
  if ((!memorySection.hidden && navMemory.hidden) || (!traceSection.hidden && navStrace.hidden)) navSession.click();
}

let socket: WebSocket | null = null;
let flowSocket: WebSocket | null = null;
let flowCount = 0;
let visibleRowCount = 0;
let splitPercent = 50;
const responseRows = new Map<string, ResponseRow>();
const websocketRows = new Map<string, { item: HTMLLIElement; firstSequence: number; messages: number; bytes: number }>();
const usageByFlow = new Map<string, ContextUsage>();
const responseChoices = new Map<string, ResponseChoice>();
const internalFlows = new Set<string>();
const requestRows = new Map<string, HTMLLIElement>();
let latestRequestFlowId: string | null = null;
let displayedUsageFlowId: string | null = null;
let hasContextMeasurement = false;
let latestContextSequence = 0;
let lastRequest: { key: string; item: HTMLLIElement; number: number; group?: HTMLElement; list?: HTMLOListElement; count: number } | null = null;
let unreadActivity = 0;

function resetReadingState(): void {
  lastRequest = null;
  unreadActivity = 0;
  newActivityButton.hidden = true;
}

function followActivity(wasAtBottom: boolean, previousTop: number, anchor?: { node: HTMLElement; top: number }): void {
  if (wasAtBottom) flowEventsElement.scrollTop = compactView ? 0 : flowEventsElement.scrollHeight;
  else {
    const shift = anchor?.node.isConnected && anchor.node.getBoundingClientRect().height > 0
      ? anchor.node.getBoundingClientRect().top - anchor.top : 0;
    flowEventsElement.scrollTop = previousTop + shift;
    unreadActivity += 1;
    newActivityButton.hidden = false;
    newActivityButton.textContent = `New activity (${unreadActivity}) · Jump to latest`;
  }
}

newActivityButton.addEventListener("click", () => {
  flowEventsElement.scrollTop = compactView ? 0 : flowEventsElement.scrollHeight;
  unreadActivity = 0;
  newActivityButton.hidden = true;
});

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
  provider?: string;
  context_visibility?: { scope: string; previous_response_id: string | null; predecessor_observed: boolean; server_context: string };
  request_operation?: string;
  detail_url?: string;
  body_digest?: string;
  request_number?: number;
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
  occurred_at?: string | null;
  provider?: string;
  kind: "context.usage";
  flow_id: string;
  sequence: number;
  stream_identity: { stream_id: string; confidence: string };
  used_input_tokens: number | null;
  components: { input_tokens: number | null; cache_creation_input_tokens?: number; cache_read_input_tokens?: number; cached_input_tokens?: number | null; output_tokens?: number | null; reasoning_output_tokens?: number | null };
  context_window_tokens: number | null;
  context_window_source: string;
  percent: number | null;
  usage_source: string;
};

type ContextResponse = {
  provider?: string;
  correlation?: { basis: string; confidence: string };
  detail_url?: string;
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
  statusElement.title = "";
  statusElement.dataset.state = state;
}

function sendResize(): void {
  if (!requestTabs.isLive) return;
  fit.fit();
  sizeElement.textContent = `${terminal.cols} × ${terminal.rows}`;
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "resize", rows: terminal.rows, cols: terminal.cols }));
  }
}

function detachSockets(): void {
  socket = null;
  closeFlowConnection();
}

function forgetSession(): void {
  detachSockets();
  if (sessionId !== null) localStorage.removeItem(`${CONTEXT_CURSOR_PREFIX}${sessionId}`);
  localStorage.removeItem(SESSION_STORAGE_KEY);
  sessionId = null;
  selectedSessionModel = null;
  selectedLaunch = {};
  applyLaunchCapabilities(selectedLaunch);
  startButton.disabled = false;
  startButton.textContent = "Start session";
  stopButton.disabled = true;
}

function resetContextView(): void {
  receivedContextEvents.clear();
  resetReadingState();
  flowCount = 0;
  visibleRowCount = 0;
  responseRows.clear();
  websocketRows.clear();
  usageByFlow.clear();
  drawContextHistory();
  responseChoices.clear();
  internalFlows.clear();
  requestRows.clear();
  latestRequestFlowId = null;
  displayedUsageFlowId = null;
  hasContextMeasurement = false;
  latestContextSequence = 0;
  clearHistoryButton.disabled = true;
  contextMeterProgress.value = 0;
  contextMeterProgress.removeAttribute("aria-valuetext");
  contextMeterProgress.textContent = "No measurement";
  meterStatus.textContent = "No measured response yet";
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
  if (event.kind === "websocket.message") {
    const body = event.payload.body as { wire?: { byte_length?: number } } | undefined;
    const direction = event.payload.direction === "client_to_server" ? "client → server" : "server → client";
    return `${direction} · ${String(event.payload.message_type ?? "message")} message ${String(event.payload.message_index ?? "")} · ${Number(body?.wire?.byte_length ?? 0).toLocaleString()} bytes`;
  }
  if (event.kind === "websocket.closed") return `WebSocket closed · ${String(event.payload.message_count)} messages · archive ${String(event.payload.archive_status)}`;
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

function renderCompactBatch(events: Array<ContextDiff | ContextResponse | ContextUsage>, mode: "initial" | "older" | "live", total: number, next: number | null, usage?: ContextUsage): void {
  const top = flowEventsElement.scrollTop;
  const height = flowEventsElement.scrollHeight;
  const following = top < 48;
  const previousLastRequest = lastRequest;
  const previousMeterStatus = meterStatus.textContent;
  const previousMeterDetail = contextMeterDetail.textContent;
  if (mode !== "live") lastRequest = null;
  batchRendering = true;
  try {
    for (const event of events) {
      const key = `${event.sequence}:${event.kind}:${event.flow_id}`;
      if (receivedContextEvents.has(key)) continue;
      if (event.kind === "context.response" && !requestRows.has(event.flow_id)) continue;
      if (event.kind === "context.diff") { renderContextDiff(event); if (mode === "live") requestTabs.activity(); }
      else if (event.kind === "context.response") renderContextResponse(event);
      else renderContextUsage(event);
      receivedContextEvents.add(key);
      latestContextSequence = Math.max(latestContextSequence, event.sequence);
    }
    if (usage) showContextUsage(usage);
    const sorted = [...flowEventsElement.children].sort((a, b) => Number((b as HTMLElement).dataset.order) - Number((a as HTMLElement).dataset.order));
    flowEventsElement.append(...sorted);
  } finally { batchRendering = false; }
  drawContextHistory();
  if (mode === "older") {
    lastRequest = previousLastRequest;
    meterStatus.textContent = previousMeterStatus;
    contextMeterDetail.textContent = previousMeterDetail;
  }
  flowCountElement.textContent = `${requestRows.size} of ${total} requests · newest first`;
  olderButton.hidden = next === null;
  if (mode === "initial" || (mode === "live" && following)) flowEventsElement.scrollTop = 0;
  else if (mode === "older") flowEventsElement.scrollTop = top;
  else {
    flowEventsElement.scrollTop = top + flowEventsElement.scrollHeight - height;
    unreadActivity += events.length;
    newActivityButton.hidden = false;
    newActivityButton.textContent = `New activity (${unreadActivity}) · Jump to latest`;
  }
}

function startContextConnection(id: string, scheme: string): void {
  closeFlowConnection();
  compactView = true;
  const saved = Number.parseInt(localStorage.getItem(`${CONTEXT_CURSOR_PREFIX}${id}`) ?? "0", 10);
  const after = Number.isSafeInteger(saved) && saved >= 0 ? saved : 0;
  fastContext = new FastContext(id, after, renderCompactBatch,
    message => { captureStatus.textContent = message; },
    () => { compactView = false; olderButton.hidden = true; connectFlowSocket(id, scheme); });
  void fastContext.start();
}

function comparisonGroup(diff: ContextDiff): HTMLElement {
  const row = textElement("p", "comparison-group", "");
  row.title = "Backend grouping key: comparison_lineage. This selects comparison history within the capture session; it is not necessarily a unique conversation or confirmed agent ID.";
  row.append(textElement("span", "comparison-group-label", "Comparison group"), textElement("code", "comparison-group-key", diff.comparison_lineage || "unavailable"));
  return row;
}

function renderContextDiff(diff: ContextDiff, existing?: HTMLLIElement): void {
  if (!existing && requestRows.has(diff.flow_id)) return;
  if (!existing) {
  if (!batchRendering) requestTabs.activity();
  flowCount += 1;
  visibleRowCount += 1;
  flowEmptyElement.hidden = true;
  clearHistoryButton.disabled = false;
  latestRequestFlowId = diff.flow_id;
  if (hasContextMeasurement) {
    meterStatus.textContent = "Previous measurement · new request observed";
    contextMeterDetail.textContent = `Showing the previous completed measurement while request ${diff.flow_id} awaits response usage · ${diff.metrics.body_bytes.toLocaleString()} exact request bytes.`;
  } else {
    contextMeterValue.textContent = "Awaiting response usage";
    meterStatus.textContent = "No measured response yet";
    contextMeterDetail.textContent = `Request ${diff.flow_id} · ${diff.metrics.body_bytes.toLocaleString()} exact bytes. Bytes are not converted into tokens.`;
  }
  }
  const item = document.createElement("li");
  item.dataset.order = String(diff.request_number ?? existing?.dataset.order ?? flowCount);
  item.className = `flow-event context-diff relationship-${diff.relationship}`;
  if (diff.request_operation === "token_count" || diff.request_purpose.classification.startsWith("likely_internal_")) {
    item.classList.add("purpose-internal");
    item.dataset.purpose = diff.request_purpose.classification;
    if (!existing) internalFlows.add(diff.flow_id);
  }
  const header = document.createElement("header");
  header.append(textElement("span", "event-sequence", `Request ${item.dataset.order}`));
  const titles = { initial: "Initial context", chronological: "Context updated", retry_or_duplicate: "Unchanged context", compaction_candidate: "Possible compaction" };
  header.append(textElement("strong", "event-kind", diff.request_operation === "token_count" ? "Token count · ancillary request" : titles[diff.relationship]));
  header.append(textElement("span", "event-time", `${diff.metrics.body_bytes.toLocaleString()} bytes`));
  const countSummary = `+${diff.counts.added} added · −${diff.counts.removed} removed · ~${diff.counts.transformed} changed · =${diff.counts.retained} retained`;
  item.append(header, textElement("p", "event-summary context-counts", countSummary));
  item.append(comparisonGroup(diff));
  if (diff.context_visibility) {
    const reference = diff.context_visibility.previous_response_id;
    item.append(textElement("p", "comparison-label context-visibility", `Captured request fields only; server-held context is not reconstructed. ${reference ? `Previous response: ${reference} (${diff.context_visibility.predecessor_observed ? "observed predecessor; comparison covers request fields only" : "predecessor not captured"}).` : "No captured continuation reference; no conversation relationship inferred."}`));
  }
  item.append(textElement("p", "comparison-label", diff.predecessor_flow_id === null ? "First observed context" : diff.predecessor_confidence === "none" ? "Comparison: chronological · attribution unknown" : `Comparison confidence: ${diff.predecessor_confidence}`));
  if (!existing) {
    const inspect = document.createElement("button");
    inspect.type = "button"; inspect.className = "inspect-request secondary-button";
    inspect.textContent = "Inspect changes & request evidence";
    const owner = sessionId;
    inspect.onclick = () => requestTabs.open(`${owner}:${diff.flow_id}`, item.dataset.order!, async (panel, signal) => {
      let detail = diff;
      if (diff.detail_url) {
        const response = await fetch(diff.detail_url, { cache: "no-store", signal });
        if (!response.ok) throw new Error("Request unavailable");
        detail = await response.json();
      }
      if (signal.aborted) return;
      const evidence = document.createElement("li"); evidence.className = "flow-event request-detail";
      evidence.dataset.order = item.dataset.order;
      renderContextDiff({ ...detail, detail_url: undefined }, evidence);
      evidence.querySelector(".response-awaiting")?.remove();
      const list = document.createElement("ul"); list.className = "request-detail-list"; list.append(evidence);
      panel.replaceChildren(list);
      addPayloadDiff(panel, list, detail, owner!, signal);
    });
    item.append(inspect);
    item.append(textElement("p", "response-awaiting", diff.request_operation === "token_count" ? "Token-count endpoint · excluded from generation baselines" : "No captured response available"));
    requestRows.set(diff.flow_id, item);
    appendRequest(item, diff);
    updateCount();
    return;
  }
  const metadata = disclosure(item, "Evidence & attribution", "request-evidence");
  if (diff.request_operation === "token_count") metadata.append(textElement("p", "context-provenance", "Token-count operation identified by captured POST URL. This request is compared only with token-count requests, not model-generation context."));
  metadata.append(textElement("p", "context-provenance", "Request only · normalized from the captured API request. Response content is not included in these change blocks."));
  metadata.append(textElement("p", `request-purpose confidence-${diff.request_purpose.confidence}`, `Request purpose: ${diff.request_purpose.classification.replaceAll("_", " ")} · ${diff.request_purpose.confidence} confidence · lineage ${diff.comparison_lineage} · ${diff.request_purpose.evidence.join(", ")}`));
  metadata.append(textElement("p", `stream-identity confidence-${diff.stream_identity.confidence}`, `Stream: ${diff.stream_identity.stream_id} · ${diff.stream_identity.confidence} confidence`));
  metadata.append(textElement("p", "context-metrics", `Wire event sequence: ${diff.sequence} · Flow: ${diff.flow_id}`));
  const harnessBlockCount = diff.changes.flatMap((change) => [change.before, change.after])
    .filter((block) => typeof block?.origin === "string" && block.origin.startsWith("harness_injected_")).length;
  if (harnessBlockCount > 0) {
    metadata.append(textElement("p", "harness-origin-summary", `${harnessBlockCount} changed-side block observation${harnessBlockCount === 1 ? "" : "s"} classified as harness-injected; expand changes for origin evidence.`));
  }
  const tokens = diff.metrics.token_count === null
    ? "Token count unavailable in request"
    : `${diff.metrics.token_count.toLocaleString()} tokens (${diff.metrics.token_count_source})`;
  metadata.append(textElement("p", "context-metrics", tokens));
  if (diff.predecessor_flow_id !== null) {
    metadata.append(textElement("p", "comparison-confidence", `Compared by ${diff.predecessor_basis.replaceAll("_", " ")} · ${diff.predecessor_confidence} confidence · predecessor ${diff.predecessor_flow_id}`));
  }
  for (const changeKind of ["added", "removed", "transformed", "retained"] as const) {
    const changes = diff.changes.filter((change) => change.change === changeKind);
    if (!changes.length) continue;
    const label = changeKind === "transformed" ? "Changed" : changeKind[0].toUpperCase() + changeKind.slice(1);
    const group = disclosure(item, `${label} blocks (${changes.length})`, `change-${changeKind}`);
    group.open = changeKind !== "retained" && changes.length <= 3;
    let built = false;
    const buildBlocks = () => {
    if (!group.open || built) return;
    built = true;
    for (const change of changes) {
      const block = change.after ?? change.before;
      const title = `${String(block?.role ?? block?.category ?? "Block")} · ${String(block?.kind ?? "content")} · ${String(block?.path ?? "")}${change.moved ? " · moved" : ""}`;
      const content = disclosure(group, title, "change-block");
      content.open = changes.length <= 3 && changeKind !== "retained";
      let rendered = false;
      const render = () => {
        if (!content.open || rendered) return;
        rendered = true;
        if (changeKind === "transformed") {
          readableChange(content, change.before, change.after);
        } else readableBlock(content, block, changeKind === "removed" ? "Removed" : "Content");
        addEvidence(content, "Block metadata & raw values", change, "metadata");
      };
      content.addEventListener("toggle", render);
      render();
    }
    };
    group.addEventListener("toggle", buildBlocks);
    buildBlocks();
  }
  addEvidence(metadata, "Exact captured request fields", diff.exact_request, "exact");
  item.append(metadata);
  const responsePlaceholder = textElement("p", "response-awaiting", "No captured response available");
  responsePlaceholder.dataset.flowId = diff.flow_id;
  item.append(responsePlaceholder);
  if (existing) {
    const response = existing.querySelector(".model-response");
    if (response) { item.querySelector(".response-awaiting")?.remove(); item.append(response); }
    existing.replaceChildren(...item.childNodes);
    return;
  }
  requestRows.set(diff.flow_id, item);
  appendRequest(item, diff);
  updateCount();
}

function appendRequest(item: HTMLLIElement, diff: ContextDiff): void {
  const body = diff.exact_request.body as { decoded?: { value?: unknown } } | undefined;
  const key = diff.body_digest ? JSON.stringify([diff.comparison_lineage, diff.stream_identity.stream_id, diff.body_digest]) : body?.decoded?.value === undefined ? "" : JSON.stringify([diff.comparison_lineage, diff.stream_identity.stream_id, body.decoded.value]);
  if (key && lastRequest?.key === key && Number(item.dataset.order) === lastRequest.number + lastRequest.count && diff.relationship === "retry_or_duplicate"
      && diff.counts.added === 0 && diff.counts.removed === 0 && diff.counts.transformed === 0) {
    if (!lastRequest.group) {
      const group = document.createElement("li");
      group.className = "repeat-group";
      const details = disclosure(group, "", "repeat-disclosure");
      group.append(comparisonGroup(diff));
      if (!batchRendering) {
        const bounds = lastRequest.item.getBoundingClientRect();
        const viewport = flowEventsElement.getBoundingClientRect();
        const readingOlder = flowEventsElement.scrollHeight - flowEventsElement.scrollTop - flowEventsElement.clientHeight >= 48;
        details.open = readingOlder && bounds.bottom > viewport.top && bounds.top < viewport.bottom;
      }
      details.append(textElement("p", "comparison-label", "Matching captured request bodies; this does not establish why they repeated."));
      const list = document.createElement("ol");
      list.className = "repeat-requests";
      lastRequest.item.replaceWith(group);
      list.append(lastRequest.item);
      details.append(list);
      lastRequest.group = group;
      lastRequest.list = list;
      const response = lastRequest.item.querySelector<HTMLElement>(".model-response");
      if (response) {
        const preview = document.createElement("section");
        preview.className = "group-reply";
        preview.dataset.flowId = response.dataset.flowId;
        preview.append(textElement("h3", "model-response-title", `Request ${lastRequest.number} · Model reply`));
        preview.append(textElement("p", "comparison-label", "Reconstructed from captured response · open response for full evidence"));
        responseShortcut(response, preview);
        for (const text of response.querySelectorAll(":scope > .readable-text")) preview.append(text.cloneNode(true));
        if (!preview.querySelector(".readable-text")) preview.append(textElement("p", "", "Non-text response available in response tab"));
        group.append(preview);
      }
    }
    lastRequest.count += 1;
    lastRequest.group.dataset.order = item.dataset.order;
    lastRequest.list!.append(item);
    lastRequest.group.querySelector("summary")!.textContent = `Requests ${lastRequest.number}–${item.dataset.order} · ${lastRequest.count} matching requests`;
  } else {
    flowEventsElement.append(item);
    lastRequest = { key, item, number: Number(item.dataset.order), count: 1 };
  }
}

function responseSection(response: ContextResponse, full = false): HTMLElement {
  const section = document.createElement("section");
  section.className = "model-response";
  section.dataset.flowId = response.flow_id;
  section.append(textElement("h3", "model-response-title", "Model reply"));
  section.append(textElement("p", "comparison-label", "Reconstructed from captured response"));
  // Retain captured block order; non-text content has its own disclosure.
  for (const block of response.response.content_blocks) {
    if (block.type === "text") { readableValue(section, block, false); continue; }
    const content = disclosure(section, block.type === "thinking" ? "Thinking" : `Response block · ${String(block.type ?? "unknown")}`);
    if (full && block.type === "tool_use") content.open = true;
    if (full && typeof block.id === "string") content.append(textElement("p", "comparison-label", `Block ID: ${block.id}`));
    readableValue(content, block);
  }
  if (!full) return section;
  section.append(textElement("p", "response-identifiers", `Flow: ${response.flow_id} · Message: ${response.response.message_id ?? "unavailable"}`));
  const evidence = disclosure(section, "Response evidence", "response-evidence");
  evidence.append(textElement("p", "response-provenance", response.provider === "codex"
    ? `Response only · readable output derived from captured Responses events. Pairing: ${response.correlation?.basis ?? "unknown"} (${response.correlation?.confidence ?? "none"} confidence). ${response.exact_response.transport === "websocket" ? "Logical WebSocket message" : "HTTP response"} bytes are preserved below.`
    : "Response only · semantic blocks reconstructed from the completed captured SSE stream, correlated by exact flow_id."));
  evidence.append(textElement("p", `response-purpose confidence-${response.purpose.confidence}`, `Purpose: ${response.purpose.classification.replaceAll("_", " ")} · ${response.purpose.confidence} confidence · ${response.purpose.evidence.join(", ")}`));
  const metadata = [
    response.response.model ?? "unknown model",
    response.response.stop_reason ? `stop: ${response.response.stop_reason}` : "stop reason unavailable",
    response.response.output_tokens === null ? "output tokens unavailable" : `${response.response.output_tokens.toLocaleString()} output tokens`,
  ].join(" · ");
  evidence.append(textElement("p", "response-metadata", metadata));
  addEvidence(evidence, `Reconstructed response content blocks (${response.response.content_blocks.length})`, response.response.content_blocks, "interpreted");
  const exactBody = response.exact_response.body as { wire?: unknown; decoded?: unknown; decode_status?: unknown } | undefined;
  const exactWire = { ...response.exact_response, body: { wire: exactBody?.wire } };
  addEvidence(evidence, "Exact captured response metadata and wire bytes", exactWire, "exact");
  if (response.exact_response.transport !== "websocket") addEvidence(evidence, "Losslessly decoded response SSE", { decoded: exactBody?.decoded, decode_status: exactBody?.decode_status }, "interpreted");
  return section;
}

function responseShortcut(source: HTMLElement, target: HTMLElement): void {
  const original = source.querySelector<HTMLButtonElement>(".inspect-response");
  if (!original) return;
  const shortcut = original.cloneNode(true) as HTMLButtonElement;
  shortcut.onclick = () => original.click(); target.append(shortcut);
}

function renderContextResponse(response: ContextResponse): void {
  const item = requestRows.get(response.flow_id);
  if (!item) return;
  item.querySelector(".response-awaiting")?.remove();
  item.querySelector(".model-response")?.remove();
  const section = responseSection(response);
  const inspect = document.createElement("button"); inspect.type = "button"; inspect.className = "inspect-response secondary-button";
  inspect.textContent = "Read full reply & response evidence";
  const owner = sessionId, number = item.dataset.order!;
  responseChoices.set(response.flow_id, { number: Number(number), response });
  inspect.onclick = () => requestTabs.open(`${owner}:${response.flow_id}`, number, async (panel, signal) => {
    let detail = response;
    if (response.detail_url) {
      const result = await fetch(response.detail_url, { cache: "no-store", signal });
      if (!result.ok) throw new Error("Response unavailable");
      detail = await result.json();
    }
    if (signal.aborted) return;
    const content = responseSection(detail, true); content.classList.add("response-detail");
    addResponsePayload(panel, content, detail, [...responseChoices.values()]
      .filter(choice => choice.number < Number(number) && owner === sessionId).sort((a, b) => b.number - a.number), signal);
  }, "Response");
  section.append(inspect);
  item.append(section);
  const group = item.closest(".repeat-group");
  if (group) {
    // A reply must stay visible even when its repeated requests are collapsed.
    const preview = document.createElement("section");
    preview.className = "group-reply";
    preview.dataset.flowId = response.flow_id;
    preview.append(textElement("h3", "model-response-title", `${item.querySelector('.event-sequence')!.textContent} · Model reply`));
    preview.append(textElement("p", "comparison-label", "Reconstructed from captured response · open response for full evidence"));
    responseShortcut(section, preview);
    const texts = response.response.content_blocks.filter(block => block.type === "text");
    texts.forEach(block => readableValue(preview, block, false));
    if (!texts.length) preview.append(textElement("p", "", "Non-text response available in response tab"));
    for (const existing of group.querySelectorAll<HTMLElement>(":scope > [data-flow-id]")) {
      if (existing.dataset.flowId === response.flow_id) existing.remove();
    }
    group.append(preview);
  }
  if (response.purpose.classification.startsWith("likely_internal_")) {
    item.classList.add("purpose-internal");
    item.dataset.purpose = response.purpose.classification;
    internalFlows.add(response.flow_id);
    if (!batchRendering) drawContextHistory();
    if (displayedUsageFlowId === response.flow_id) {
      const replacement = [...usageByFlow.values()]
        .filter((usage) => !internalFlows.has(usage.flow_id))
        .sort((left, right) => right.sequence - left.sequence)[0];
      if (replacement) showContextUsage(replacement);
    }
  }
}

function showContextUsage(usage: ContextUsage): void {
  meterStatus.textContent = usage.used_input_tokens === null ? "Latest response · usage unavailable" : "Latest measured request · excludes classified internal calls";
  hasContextMeasurement = usage.used_input_tokens !== null;
  displayedUsageFlowId = usage.flow_id;
  const count = (value: number | null | undefined) => value == null ? "unknown" : value.toLocaleString();
  const measured = usage.used_input_tokens != null;
  const knownLimit = usage.percent != null && usage.context_window_tokens != null && measured;
  contextMeterProgress.value = knownLimit ? usage.percent! : 0;
  contextMeterProgress.textContent = knownLimit ? `${usage.percent!.toFixed(1)}%` : "Context limit unknown";
  contextMeterProgress.setAttribute("aria-valuetext", knownLimit ? `${count(usage.used_input_tokens)} of ${count(usage.context_window_tokens)} tokens` : `Input ${count(usage.used_input_tokens)} tokens; context limit unknown`);
  contextMeterValue.textContent = knownLimit ? `${count(usage.used_input_tokens)} / ${count(usage.context_window_tokens)} tokens · ${usage.percent!.toFixed(1)}%` : `${measured ? count(usage.used_input_tokens) + " input tokens" : "Usage unknown"} · context limit unknown`;
  const components = usage.provider === "codex"
    ? `Input ${count(usage.components.input_tokens)} (cached subset ${count(usage.components.cached_input_tokens)}); output ${count(usage.components.output_tokens)} (reasoning subset ${count(usage.components.reasoning_output_tokens)}).`
    : `Uncached ${count(usage.components.input_tokens)} + cache creation ${count(usage.components.cache_creation_input_tokens)} + cache read ${count(usage.components.cache_read_input_tokens)}.`;
  contextMeterDetail.textContent = `Latest measured request not classified as internal · flow ${usage.flow_id}. ${components} Usage: ${usage.usage_source}; limit: ${usage.context_window_source}.`;
}

function drawContextHistory(): void {
  renderContextHistory([...usageByFlow.values()].filter(usage => !internalFlows.has(usage.flow_id)));
}

function renderContextUsage(usage: ContextUsage): void {
  usageByFlow.set(usage.flow_id, usage);
  if (!batchRendering) drawContextHistory();
  if (internalFlows.has(usage.flow_id)) return;
  const displayed = displayedUsageFlowId === null ? undefined : usageByFlow.get(displayedUsageFlowId);
  if (!displayed || internalFlows.has(displayed.flow_id) || usage.sequence >= displayed.sequence) {
    showContextUsage(usage);
  }
}

function updateCount(): void {
  if (batchRendering) return;
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

function updateWebSocketRow(event: FlowEvent): boolean {
  if (event.kind !== "websocket.message" || !event.flow_id) return false;
  let row = websocketRows.get(event.flow_id);
  if (!row) {
    const item = createEventRow(event);
    row = { item, firstSequence: event.sequence, messages: 0, bytes: 0 };
    websocketRows.set(event.flow_id, row);
    flowEventsElement.append(item);
  }
  row.messages += 1;
  const body = event.payload.body as { wire?: { byte_length?: number } } | undefined;
  row.bytes += Number(body?.wire?.byte_length ?? 0);
  const kind = row.item.querySelector<HTMLElement>(".event-kind")!;
  const sequence = row.item.querySelector<HTMLElement>(".event-sequence")!;
  const summary = row.item.querySelector<HTMLElement>(".event-summary")!;
  const time = row.item.querySelector<HTMLTimeElement>(".event-time")!;
  sequence.textContent = row.firstSequence === event.sequence ? `#${event.sequence}` : `#${row.firstSequence}–${event.sequence}`;
  kind.textContent = "Codex WebSocket connection";
  time.textContent = new Date(event.occurred_at).toLocaleTimeString();
  summary.textContent = `${row.messages} logical messages · ${row.bytes.toLocaleString()} bytes observed · latest: ${summarize(event)}`;
  const direction = event.payload.direction === "client_to_server" ? "client to server" : "server to client";
  const messageType = String(event.payload.message_type ?? "message");
  const messageIndex = String(event.payload.message_index ?? row.messages - 1);
  const messageBody = event.payload.body as { wire?: unknown; decoded?: unknown } | undefined;
  if (messageBody?.wire) addEvidence(row.item, `Message ${messageIndex} · ${direction} · exact logical ${messageType} message bytes`, messageBody.wire, "exact");
  if (messageBody?.decoded) addEvidence(row.item, `Message ${messageIndex} · interpreted JSON message`, messageBody.decoded, "interpreted");
  addEvidence(row.item, `Message ${messageIndex} · event metadata`, {
    flow_id: event.flow_id,
    direction: event.payload.direction,
    message_type: event.payload.message_type,
    timestamp: event.payload.timestamp,
    sanitization: event.sanitization,
  }, "metadata");
  return true;
}

function renderFlowEvent(event: FlowEvent): void {
  flowCount += 1;
  flowEmptyElement.hidden = true;
  if (updateResponseRow(event)) {
    updateCount();
    return;
  }
  if (updateWebSocketRow(event)) {
    updateCount();
    return;
  }
  const item = createEventRow(event);
  setEvidence(item, event, true);
  flowEventsElement.append(item);
  item.scrollIntoView({ block: "nearest" });
  updateCount();
}

function connectFlowSocket(id: string, scheme: string, recovering = false): void {
  closeFlowConnection();
  const generation = flowGeneration;
  const savedCursor = Number.parseInt(localStorage.getItem(`${CONTEXT_CURSOR_PREFIX}${id}`) ?? "0", 10);
  const clearedThrough = Number.isSafeInteger(savedCursor) && savedCursor >= 0 ? savedCursor : 0;
  // Completion can yield usage and response at the same sequence. Replay that
  // boundary and deduplicate by sequence/kind/flow, not sequence alone.
  const afterSequence = recovering ? Math.max(clearedThrough, latestContextSequence - 1) : clearedThrough;
  if (!recovering) {
    latestContextSequence = afterSequence;
    flowRetryCount = 0;
  }
  captureStatus.textContent = recovering ? "Context: reconnecting…" : "Context: connecting…";
  flowSocket = new WebSocket(`${scheme}://${location.host}/api/sessions/${id}/contexts?after_sequence=${afterSequence}`);
  const connectedFlowSocket = flowSocket;
  const retry = () => {
    if (generation !== flowGeneration || sessionId !== id || flowRetryTimer !== undefined) return;
    captureStatus.textContent = "Context: disconnected · retrying…";
    flowRetryTimer = window.setTimeout(() => {
      flowRetryTimer = undefined;
      if (generation === flowGeneration && sessionId === id) connectFlowSocket(id, scheme, true);
    }, Math.min(1000 * 2 ** flowRetryCount++, 10000));
  };
  flowSocket.addEventListener("open", () => {
    if (flowSocket === connectedFlowSocket) captureStatus.textContent = "Context: connected";
  });
  flowSocket.addEventListener("message", (message) => {
    if (flowSocket !== connectedFlowSocket) return;
    try {
    const event = JSON.parse(String(message.data)) as ContextDiff | ContextUsage | ContextResponse | { type: string; message: string };
    if ("type" in event) {
      captureStatus.textContent = "Context: capture record error · recovering…";
      flowSocket = null;
      connectedFlowSocket.close();
      retry();
      return;
    }
    const eventKey = `${event.sequence}:${event.kind}:${event.flow_id}`;
    if (receivedContextEvents.has(eventKey)) return;
    const previousTop = flowEventsElement.scrollTop;
    const atBottom = flowEventsElement.scrollHeight - previousTop - flowEventsElement.clientHeight < 48;
    const viewportTop = flowEventsElement.getBoundingClientRect().top;
    const node = [...flowEventsElement.querySelectorAll<HTMLElement>("summary, .readable-text, header")]
      .find(element => { const bounds = element.getBoundingClientRect(); return bounds.height > 0 && bounds.bottom > viewportTop; });
    const anchor = node ? { node, top: node.getBoundingClientRect().top } : undefined;
    if (event.kind === "context.usage") renderContextUsage(event);
    else if (event.kind === "context.response") renderContextResponse(event);
    else renderContextDiff(event);
    followActivity(atBottom, previousTop, anchor);
    receivedContextEvents.add(eventKey);
    latestContextSequence = Math.max(latestContextSequence, event.sequence);
    flowRetryCount = 0;
    if (flowRetryTimer === undefined) captureStatus.textContent = "Context: connected";
    } catch {
      captureStatus.textContent = "Context: update failed · recovering…";
      flowSocket = null;
      connectedFlowSocket.close();
      retry();
    }
  });
  flowSocket.addEventListener("close", retry);
  flowSocket.addEventListener("error", () => {
    if (flowSocket === connectedFlowSocket) { connectedFlowSocket.close(); retry(); }
  });
}

function clearContextHistory(): void {
  if (sessionId === null) return;
  usageByFlow.clear();
  drawContextHistory();
  responseChoices.clear();
  resetReadingState();
  localStorage.setItem(`${CONTEXT_CURSOR_PREFIX}${sessionId}`, String(latestContextSequence));
  responseRows.clear();
  websocketRows.clear();
  requestRows.clear();
  flowCount = 0;
  visibleRowCount = 0;
  flowEventsElement.replaceChildren();
  flowEmptyElement.hidden = false;
  flowCountElement.textContent = "0 requests";
  clearHistoryButton.disabled = true;
  if (compactView) startContextConnection(sessionId, location.protocol === "https:" ? "wss" : "ws");
}

function connectSession(id: string, selectedModel: string | null = null, launch: { harness?: string | null; auth_mode?: string | null; capabilities?: string[] } = {}): void {
  selectedLaunch = launch;
  applyLaunchCapabilities(launch);
  const harnessLabel = launch.harness === "codex" ? "Codex" : "Claude";
  document.querySelector<HTMLHeadingElement>("#terminal-title")!.textContent = `${harnessLabel} CLI`;
  document.querySelector<HTMLDivElement>("#terminal")!.setAttribute("aria-label", `Interactive ${harnessLabel} terminal`);
  const authLabel = launch.auth_mode ? ` · ${launch.auth_mode === "vertex" ? "Vertex" : "OAuth"}` : "";
  sessionId = id;
  selectedSessionModel = selectedModel;
  localStorage.setItem(SESSION_STORAGE_KEY, id);
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  startContextConnection(id, scheme);
  socket?.close();
  socket = new WebSocket(`${scheme}://${location.host}/api/sessions/${id}/terminal`);
  const connectedSocket = socket;
  socket.binaryType = "arraybuffer";
  socket.addEventListener("open", () => {
    if (socket !== connectedSocket) return;
    startButton.disabled = true;
    startButton.textContent = "Connected";
    stopButton.disabled = false;
    setStatus(`${harnessLabel} connected${authLabel}${selectedModel ? ` · ${selectedModel}` : ""}`, "active");
    statusElement.title = selectedModel ? "Model selected at session launch; changes made with /model are not reflected here." : "";
    sendResize();
    if (requestTabs.isLive) terminal.focus();
  });
  socket.addEventListener("message", (event) => {
    if (event.data instanceof ArrayBuffer) {
      terminal.write(new Uint8Array(event.data));
      return;
    }
    const message = JSON.parse(String(event.data)) as { type?: string; exit_code?: number | null; message?: string };
    if (message.type === "exit") {
      setStatus(`${harnessLabel} exited (${message.exit_code ?? "unknown"})`);
      forgetSession();
    } else if (message.type === "error") {
      setStatus(message.message ?? "Terminal error", "error");
    }
  });
  socket.addEventListener("close", () => {
    if (socket !== connectedSocket) return;
    socket = null;
    if (sessionId === id) {
      setStatus(`Browser detached; ${harnessLabel} is still running`, "idle");
      startButton.disabled = false;
      startButton.textContent = "Reconnect";
      stopButton.disabled = false;
    }
  });
  socket.addEventListener("error", () => {
    if (socket === connectedSocket) setStatus("Terminal connection error", "error");
  });
}

async function startSession(selection: LaunchSelection): Promise<string | null> {
  startButton.disabled = true;
  terminal.clear();
  setStatus("Starting containers…", "active");
  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ extra_args: [], ...selection }),
    });
    if (!response.ok) throw new Error(await response.text());
    const created = await response.json() as { session_id: string; selected_model?: string | null; harness?: string | null; auth_mode?: string | null; capabilities?: string[] };
    resetContextView();
    connectSession(created.session_id, created.selected_model ?? null, created);
    return null;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not start session";
    setStatus(message, "error");
    forgetSession();
    return message;
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

let discoveringSession = false;

async function resumePersistedSession(): Promise<void> {
  if (discoveringSession || sessionId !== null) return;
  discoveringSession = true;
  try {
    const response = await fetch("/api/sessions/active", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not discover shared session");
    const active = await response.json() as { session_id: string; alive: boolean; selected_model?: string | null; harness?: string | null; auth_mode?: string | null; capabilities?: string[] } | null;
    if (sessionId !== null) return;
    if (!active?.alive) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      setStatus("No active session");
      return;
    }
    resetContextView();
    setStatus("Joining shared session…", "active");
    connectSession(active.session_id, active.selected_model ?? null, active);
  } catch (error) {
    if (sessionId === null) setStatus(error instanceof Error ? error.message : "Session discovery failed", "error");
  } finally {
    discoveringSession = false;
  }
}

terminal.onData((data) => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "input", data }));
  }
});

new ResizeObserver(sendResize).observe(terminalElement);
const startDialog = new StartDialog(startSession);
startButton.addEventListener("click", () => {
  if (sessionId !== null) {
    terminal.clear();
    resetContextView();
    connectSession(sessionId, selectedSessionModel, selectedLaunch);
  }
  else startDialog.show();
});
stopButton.addEventListener("click", () => void stopSession());
clearHistoryButton.addEventListener("click", clearContextHistory);
window.addEventListener("beforeunload", () => {
  socket?.close();
  closeFlowConnection();
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
window.setInterval(() => { void resumePersistedSession(); }, 3000);
