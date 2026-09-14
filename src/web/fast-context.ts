/** Paged summaries and a cursor-consistent live handoff. */
export class FastContext {
  private socket: WebSocket | null = null;
  private stopped = false;
  private timer?: number;
  private failures = 0;
  private cursor = 0;
  private next: number | null = null;
  private total = 0;
  private controller = new AbortController();
  private loading = false;
  constructor(private id: string, private after: number,
    private apply: (events: any[], mode: "initial" | "older" | "live", total: number, next: number | null, usage?: any) => void,
    private status: (message: string) => void,
    private fallback: () => void) {}

  async start(): Promise<void> {
    try {
      this.status("Context: loading recent history…");
      const response = await fetch(`/api/sessions/${this.id}/context-history?after_sequence=${this.after}`, { cache: "no-store", signal: this.controller.signal });
      if (response.status === 404) { if (!this.stopped) this.fallback(); return; }
      if (!response.ok) throw new Error("History unavailable");
      const page = await response.json();
      if (this.stopped) return;
      this.cursor = page.cursor; this.next = page.next_before; this.total = page.total;
      this.apply(page.events, "initial", this.total, this.next, page.latest_usage);
      if (page.error) this.status(`Context: ${page.error}`);
      this.connect();
    } catch { if (!this.stopped) { this.status("Context: history unavailable · retrying…"); this.timer = window.setTimeout(() => { void this.start(); }, 2000); } }
  }

  async older(): Promise<void> {
    if (this.loading || this.next === null || this.stopped) return;
    this.loading = true;
    try {
      const response = await fetch(`/api/sessions/${this.id}/context-history?before=${this.next}&after_sequence=${this.after}`, { cache: "no-store", signal: this.controller.signal });
      if (!response.ok) throw new Error("History unavailable");
      const page = await response.json();
      if (this.stopped) return;
      this.next = page.next_before;
      this.apply(page.events, "older", this.total, this.next);
    } catch { if (!this.stopped) this.status("Context: older history unavailable · try again"); }
    finally { this.loading = false; }
  }

  private connect(): void {
    if (this.stopped) return;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/api/sessions/${this.id}/contexts?compact=true&cursor=${this.cursor}&after_sequence=${this.after}`);
    this.socket = socket;
    this.status("Context: connecting…");
    socket.onmessage = event => {
      if (this.stopped || this.socket !== socket) return;
      try {
        const batch = JSON.parse(event.data);
        if (batch.type !== "context-batch") throw new Error("Unexpected context data");
        const fresh = batch.events.filter((item: any) => item.cursor > this.cursor);
        const nextTotal = this.total + fresh.filter((item: any) => item.kind === "context.diff").length;
        if (fresh.length) this.apply(fresh, "live", nextTotal, this.next);
        this.total = nextTotal;
        this.cursor = batch.cursor;
        this.failures = 0;
        this.status(batch.error ? `Context: ${batch.error}` : "Context: connected");
      } catch { socket.close(); }
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      if (this.stopped || this.socket !== socket) return;
      this.status("Context: disconnected · retrying…");
      this.timer = window.setTimeout(() => this.connect(), Math.min(1000 * 2 ** this.failures++, 10000));
    };
  }

  stop(): void {
    this.stopped = true;
    this.controller.abort();
    window.clearTimeout(this.timer);
    this.socket?.close();
  }
}
