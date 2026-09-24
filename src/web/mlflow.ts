type Trace = {
  trace_id: string; state: string; request_time: string | null; duration: string | null;
  request_preview: unknown; response_preview: unknown; session_id: string | null;
  turn_id: string | null; inspector_session_id: string | null; usage: unknown; evidence: string;
  metadata: Record<string, unknown>;
};
type Span = { id: string; parent_id: string | null; name: string; type: string; start_ns: string;
  end_ns: string; status: unknown; inputs: unknown; outputs: unknown; usage: unknown; attributes: unknown };
type Detail = { trace: Trace; spans: Span[]; raw: string; source: string };
const pretty = (value: unknown) => value == null ? "Not recorded" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
function element<K extends keyof HTMLElementTagNameMap>(tag: K, text = ""): HTMLElementTagNameMap[K] {
  const result = document.createElement(tag); result.textContent = text; return result;
}
function badge(value: string): HTMLElement {
  const node = element("span", value); node.className = "mlflow-badge";
  node.dataset.kind = value.toLowerCase(); return node;
}
function timing(span: Span): { start: bigint; end: bigint } | null {
  try {
    const start = BigInt(span.start_ns), end = BigInt(span.end_ns);
    return start > 0n && end >= start ? { start, end } : null;
  } catch { return null; }
}
function elapsed(span: Span): string {
  const time = timing(span); if (!time) return "Not recorded";
  const ms = Number(time.end - time.start) / 1e6;
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Number(ms.toFixed(3))} ms`;
}
function metric(label: string, value: string): HTMLElement {
  const node = element("div"); node.className = "mlflow-metric";
  node.append(element("span", label), element("strong", value)); return node;
}
async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, cache: "no-store" });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? "Unable to load MLflow traces.");
  return body as T;
}

export class MLflowView {
  private status = document.querySelector<HTMLElement>("#mlflow-status")!;
  private list = document.querySelector<HTMLElement>("#mlflow-list")!;
  private detail = document.querySelector<HTMLElement>("#mlflow-detail")!;
  private session = document.querySelector<HTMLInputElement>("#mlflow-session")!;
  private more = document.querySelector<HTMLButtonElement>("#mlflow-more")!;
  private refresh = document.querySelector<HTMLButtonElement>("#mlflow-refresh")!;
  private auto = document.querySelector<HTMLInputElement>("#mlflow-auto")!;
  private controller: AbortController | null = null;
  private detailController: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private traces: Trace[] = [];
  private next = "";
  private selected = "";
  private visible = false;

  constructor() {
    document.querySelector<HTMLFormElement>("#mlflow-filter")!.onsubmit = event => {
      event.preventDefault(); this.selected = ""; this.detail.replaceChildren(); void this.load();
    };
    this.more.onclick = () => { this.auto.checked = false; void this.load(true); };
    this.auto.onchange = () => this.schedule();
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) this.cancelTimer(); else this.schedule();
    });
  }
  show(): void { this.visible = true; void this.load(); if (this.selected) void this.loadDetail(this.selected); }
  hide(): void {
    this.visible = false; this.cancelTimer(); this.controller?.abort(); this.detailController?.abort();
  }
  private cancelTimer(): void { if (this.timer !== null) clearTimeout(this.timer); this.timer = null; }
  private schedule(): void {
    this.cancelTimer();
    if (this.visible && !document.hidden && this.auto.checked) this.timer = setTimeout(() => void this.load(), 10000);
  }
  private async load(append = false): Promise<void> {
    this.cancelTimer(); this.controller?.abort();
    const controller = this.controller = new AbortController();
    this.refresh.disabled = true; this.more.disabled = true;
    this.status.textContent = "Loading MLflow traces…";
    try {
      const state = await get<{ available: boolean; message: string; experiment_name: string }>("/api/mlflow/status", controller.signal);
      if (!state.available) {
        this.traces = []; this.list.replaceChildren(); this.detail.replaceChildren(); this.selected = ""; this.next = "";
        this.status.textContent = state.message; return;
      }
      const params = new URLSearchParams({ session_id: this.session.value.trim() });
      if (append && this.next) params.set("page_token", this.next);
      const data = await get<{ traces: Trace[]; next_page_token: string }>(`/api/mlflow/traces?${params}`, controller.signal);
      this.traces = append ? [...new Map([...this.traces, ...data.traces].map(t => [t.trace_id, t])).values()] : data.traces;
      this.next = data.next_page_token;
      this.renderList();
      this.status.textContent = `${state.experiment_name} · ${this.traces.length} traces loaded. ${state.message}`;
      if (!this.traces.length) this.status.textContent = "No traces found. Completed turns appear after export; try refreshing or clear the session filter.";
      if (this.selected && !append && !this.traces.some(t => t.trace_id === this.selected)) {
        this.selected = ""; this.detailController?.abort(); this.detail.replaceChildren();
      }
    } catch (error) {
      if (!controller.signal.aborted) this.status.textContent = `Unable to load traces: ${error instanceof Error ? error.message : "Unknown error"}`;
    } finally {
      if (this.controller === controller) {
        this.refresh.disabled = false; this.more.disabled = !this.next; this.more.hidden = !this.next;
        this.schedule();
      }
    }
  }
  private renderList(): void {
    this.list.replaceChildren();
    for (const trace of this.traces) {
      const item = element("li");
      const button = element("button"); button.type = "button"; button.className = "mlflow-trace";
      button.setAttribute("aria-pressed", String(trace.trace_id === this.selected));
      const heading = element("div"); heading.className = "mlflow-trace-meta";
      heading.append(badge(trace.state), element("time", trace.request_time ? new Date(trace.request_time).toLocaleString() : "Time unavailable"));
      button.append(heading, element("span", pretty(trace.request_preview).slice(0, 250)),
        element("small", `${trace.duration ?? "Duration unavailable"} · Session ${trace.session_id ?? "not recorded"}`));
      button.onclick = () => { this.selected = trace.trace_id; this.renderList(); void this.loadDetail(trace.trace_id); };
      item.append(button); this.list.append(item);
    }
    const suggestions = document.querySelector<HTMLDataListElement>("#mlflow-sessions")!;
    suggestions.replaceChildren(...[...new Set(this.traces.map(t => t.session_id).filter((v): v is string => !!v))]
      .map(id => { const option = element("option"); option.value = id; return option; }));
  }
  private async loadDetail(id: string): Promise<void> {
    this.detailController?.abort(); const controller = this.detailController = new AbortController();
    this.detail.replaceChildren(element("p", "Loading trace…"));
    try {
      const data = await get<Detail>(`/api/mlflow/traces/${encodeURIComponent(id)}`, controller.signal);
      if (controller.signal.aborted || id !== this.selected) return;
      this.renderDetail(data);
    } catch (error) {
      if (!controller.signal.aborted) this.detail.replaceChildren(element("p", `Unable to load trace: ${error instanceof Error ? error.message : "Unknown error"}`));
    }
  }
  private block(title: string, value: unknown): HTMLDetailsElement {
    const block = element("details"); block.append(element("summary", title), element("pre", pretty(value))); return block;
  }
  private renderDetail(data: Detail): void {
    const trace = data.trace;
    const header = element("header"); header.className = "mlflow-detail-header";
    const title = element("div");
    const root = data.spans.find(span => !span.parent_id);
    title.append(element("small", "TRACE EXPLORER"), element("h3", root?.name ?? "Trace details"));
    const actions = element("div"); actions.className = "mlflow-detail-actions";
    const reload = element("button", "Reload trace"); reload.type = "button";
    reload.onclick = () => void this.loadDetail(trace.trace_id);
    const filter = element("button", "Show this session"); filter.type = "button"; filter.disabled = !trace.session_id;
    filter.onclick = () => { this.session.value = trace.session_id ?? ""; void this.load(); };
    actions.append(reload, filter); header.append(title, actions);
    const metrics = element("div"); metrics.className = "mlflow-metrics";
    const usage = trace.usage && typeof trace.usage === "object" ? trace.usage as Record<string, unknown> : {};
    const tokens = (key: string) => typeof usage[key] === "number" ? (usage[key] as number).toLocaleString() : "Not recorded";
    metrics.append(badge(trace.state), metric("Duration", root ? elapsed(root) : trace.duration ?? "Not recorded"),
      metric("Spans", String(data.spans.length)), metric("Input tokens", tokens("input_tokens")), metric("Output tokens", tokens("output_tokens")));
    const identifiers = element("p", `Session ${trace.session_id ?? "not recorded"} · Turn ${trace.turn_id ?? "not recorded"}`);
    identifiers.className = "mlflow-identifiers"; identifiers.title = `Trace ${trace.trace_id}`;
    this.detail.replaceChildren(header, metrics, identifiers);
    const layout = element("div"); layout.className = "mlflow-spans";
    const tree = element("ol"); tree.setAttribute("aria-label", "Trace spans");
    const navigation = element("aside"); navigation.className = "mlflow-span-nav";
    const treeHeading = element("div"); treeHeading.className = "mlflow-pane-heading";
    treeHeading.append(element("strong", "Span timeline"), element("span", `${data.spans.length} spans`));
    const search = element("input"); search.type = "search"; search.placeholder = "Find a span…";
    search.setAttribute("aria-label", "Find a span"); search.className = "mlflow-span-search";
    navigation.append(treeHeading, search, tree);
    const spanDetail = element("div"); spanDetail.className = "mlflow-span-detail";
    spanDetail.append(element("p", "Select a span to inspect its inputs and outputs."));
    const byId = new Map(data.spans.map(span => [span.id, span]));
    const depth = (span: Span): number => {
      let current = span, level = 0; const seen = new Set([span.id]);
      while (current.parent_id && byId.has(current.parent_id) && !seen.has(current.parent_id) && level < 12) {
        seen.add(current.parent_id); current = byId.get(current.parent_id)!; level++;
      }
      return Math.min(level, 12);
    };
    // Group by recorded parent IDs, with cycle/orphan fallback; no inferred parentage.
    const ordered: Span[] = [], visited = new Set<string>();
    const children = new Map<string, Span[]>();
    for (const span of data.spans) {
      if (span.parent_id) children.set(span.parent_id, [...(children.get(span.parent_id) ?? []), span]);
    }
    const roots = data.spans.filter(span => !span.parent_id || !byId.has(span.parent_id));
    for (const root of [...roots, ...data.spans]) {
      const pending = [root];
      while (pending.length) {
        const span = pending.pop()!;
        if (visited.has(span.id)) continue;
        visited.add(span.id); ordered.push(span);
        pending.push(...(children.get(span.id) ?? []).slice().reverse());
      }
    }
    const times = ordered.map(timing).filter((v): v is {start: bigint; end: bigint} => v !== null);
    const origin = times.reduce((value, time) => time.start < value ? time.start : value, times[0]?.start ?? 0n);
    const end = times.reduce((value, time) => time.end > value ? time.end : value, origin);
    const total = end - origin;
    for (const span of ordered) {
      const item = element("li"), button = element("button"); button.type = "button";
      button.className = "mlflow-span-row"; button.setAttribute("aria-label", `${span.type} · ${span.name}`);
      button.setAttribute("aria-pressed", "false"); button.dataset.name = `${span.name} ${span.type}`.toLowerCase();
      const line = element("div"); line.className = "mlflow-span-label";
      line.style.paddingInlineStart = `${depth(span) * 12}px`;
      const name = element("span", span.name); name.className = "mlflow-span-name"; name.title = span.name;
      line.append(badge(span.type), name, element("small", elapsed(span)));
      const track = element("div"); track.className = "mlflow-timing-track";
      const time = timing(span);
      if (time && total > 0n) {
        const bar = element("span"); bar.dataset.kind = span.type.toLowerCase();
        bar.style.left = `${Number((time.start - origin) * 10000n / total) / 100}%`;
        bar.style.width = `${Number((time.end - time.start) * 10000n / total) / 100}%`;
        track.append(bar); track.title = `${elapsed(span)} · timing reported by MLflow`;
      } else track.title = "Timing unavailable or zero duration";
      button.append(line, track);
      button.onclick = () => {
        tree.querySelectorAll("button").forEach(node => node.setAttribute("aria-pressed", String(node === button)));
        const heading = element("div"); heading.className = "mlflow-selected-heading";
        heading.append(badge(span.type), element("h4", span.name), element("span", elapsed(span)));
        const tabs = element("div"); tabs.className = "mlflow-detail-tabs"; tabs.setAttribute("role", "tablist");
        const content = element("div"); content.className = "mlflow-span-content";
        content.setAttribute("role", "tabpanel"); content.id = "mlflow-span-panel";
        content.tabIndex = 0;
        const show = (mode: string) => {
          tabs.querySelectorAll<HTMLButtonElement>("button").forEach(tab => {
            const selected = tab.textContent === mode;
            tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
            if (selected) content.setAttribute("aria-labelledby", tab.id);
          });
          content.replaceChildren();
          if (mode === "Inputs & outputs") {
            for (const [label, value] of [["Inputs", span.inputs], ["Outputs", span.outputs]] as const) {
              const card = element("section"); card.className = "mlflow-io-card";
              card.append(element("h5", label), element("pre", pretty(value))); content.append(card);
            }
          } else {
            const blocks = mode === "Attributes" ? [this.block("Attributes", span.attributes), this.block("Status", span.status), this.block("Token usage", span.usage)]
              : [this.block("Span data (JSON)", span)];
            for (const block of blocks) { block.open = true; content.append(block); }
          }
        };
        for (const [index, label] of ["Inputs & outputs", "Attributes", "JSON"].entries()) {
          const tab = element("button", label); tab.type = "button"; tab.setAttribute("role", "tab");
          tab.id = `mlflow-span-tab-${index}`; tab.setAttribute("aria-controls", content.id);
          tab.onclick = () => show(label); tabs.append(tab);
          tab.onkeydown = event => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const options = [...tabs.querySelectorAll<HTMLButtonElement>("button")];
            const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + options.length) % options.length;
            options[next].focus(); options[next].click();
          };
        }
        spanDetail.replaceChildren(heading, tabs, content); show("Inputs & outputs");
      };
      item.append(button); tree.append(item);
    }
    search.oninput = () => {
      tree.querySelectorAll<HTMLButtonElement>("button").forEach(button => {
        button.parentElement!.hidden = !button.dataset.name!.includes(search.value.trim().toLowerCase());
      });
    };
    tree.querySelector<HTMLButtonElement>("button")?.click();
    if (!data.spans.length) tree.append(element("li", "No spans available yet."));
    layout.append(navigation, spanDetail);
    const provenance = element("p", `${trace.evidence} · Timing and hierarchy reported by MLflow, separate from captured network requests.`);
    provenance.className = "mlflow-provenance";
    const more = this.block("Trace metadata & previews", {trace_id: trace.trace_id, session_id: trace.session_id,
      turn_id: trace.turn_id, request_preview: trace.request_preview, response_preview: trace.response_preview, usage: trace.usage, metadata: trace.metadata});
    const footer = element("div"); footer.className = "mlflow-trace-footer";
    footer.append(provenance, more, this.block("MLflow data (JSON)", data.raw));
    this.detail.append(layout, footer);
  }
}
