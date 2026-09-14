/** In-app evidence views: no extra terminal or streaming connections. */
export class RequestTabs {
  private bar = document.querySelector<HTMLElement>("#view-tabs")!;
  private live = document.querySelector<HTMLButtonElement>("#live-tab")!;
  private workspace = document.querySelector<HTMLElement>("#workspace")!;
  private views = document.querySelector<HTMLElement>("#request-views")!;
  private entries = new Map<string, { button: HTMLButtonElement; wrapper: HTMLElement; panel: HTMLElement; controller: AbortController }>();
  private active: string | null = null;
  private serial = 0;
  private unread = 0;
  private scroll = 0;

  constructor(private onLive: () => void) {
    this.live.onclick = () => this.select(null);
    this.bar.addEventListener("keydown", event => {
      const target = event.target as HTMLElement;
      if (target.getAttribute("role") !== "tab") return;
      const keys = [null, ...this.entries.keys()];
      const index = keys.indexOf(this.active);
      let next: number;
      if (event.key === "ArrowRight") next = (index + 1) % keys.length;
      else if (event.key === "ArrowLeft") next = (index + keys.length - 1) % keys.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = keys.length - 1;
      else if (event.key === "Delete" && this.active !== null) { event.preventDefault(); this.close(this.active); return; }
      else return;
      event.preventDefault(); this.select(keys[next]);
    });
  }

  get isLive(): boolean { return this.active === null; }

  activity(): void {
    if (!this.isLive) this.live.textContent = `Live session (${++this.unread} new)`;
  }

  private select(key: string | null): void {
    if (key === this.active) {
      (key === null ? this.live : this.entries.get(key)!.button).focus();
      return;
    }
    const list = document.querySelector<HTMLElement>("#flow-events")!;
    if (this.isLive && key !== null) this.scroll = list.scrollTop;
    this.active = key;
    this.workspace.hidden = key !== null;
    this.views.hidden = key === null;
    this.live.setAttribute("aria-selected", String(key === null));
    this.live.tabIndex = key === null ? 0 : -1;
    for (const [id, entry] of this.entries) {
      entry.panel.hidden = id !== key;
      entry.button.setAttribute("aria-selected", String(id === key));
      entry.button.tabIndex = id === key ? 0 : -1;
    }
    if (key === null) {
      this.unread = 0; this.live.textContent = "Live session";
      list.scrollTop = this.scroll;
      this.onLive();
    }
    const button = key === null ? this.live : this.entries.get(key)!.button;
    button.focus(); button.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  private close(key: string): void {
    const entry = this.entries.get(key);
    if (!entry) return;
    const keys = [...this.entries.keys()];
    const index = keys.indexOf(key);
    const wasActive = this.active === key;
    entry.controller.abort(); entry.wrapper.remove(); entry.panel.remove(); this.entries.delete(key);
    if (wasActive) this.select(keys[index + 1] ?? keys[index - 1] ?? null);
  }

  open(key: string, number: string, load: (panel: HTMLElement, signal: AbortSignal) => Promise<void>): void {
    if (this.entries.has(key)) { this.select(key); return; }
    const id = `request-view-${++this.serial}`;
    const wrapper = document.createElement("span"); wrapper.className = "request-tab"; wrapper.setAttribute("role", "presentation");
    const button = document.createElement("button"); button.type = "button"; button.textContent = `Request #${number}`;
    button.id = `${id}-tab`; button.setAttribute("role", "tab"); button.setAttribute("aria-controls", id);
    button.onclick = () => this.select(key);
    const close = document.createElement("button"); close.type = "button"; close.textContent = "×"; close.className = "tab-close";
    close.setAttribute("aria-label", `Close Request #${number}`); close.title = `Close Request #${number}`;
    close.onclick = () => { const focused = wrapper.contains(document.activeElement); this.close(key); if (focused) (this.active === null ? this.live : this.entries.get(this.active)!.button).focus(); };
    wrapper.append(button, close); this.bar.append(wrapper);
    const panel = document.createElement("section"); panel.id = id; panel.className = "request-view";
    panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", button.id); panel.tabIndex = 0;
    const heading = document.createElement("h2"); heading.textContent = `Request #${number}`;
    const content = document.createElement("div"); panel.append(heading, content); this.views.append(panel);
    const controller = new AbortController(); this.entries.set(key, { button, wrapper, panel, controller });
    this.select(key);
    const run = async () => {
      content.textContent = "Loading request evidence…";
      try { await load(content, controller.signal); }
      catch {
        if (controller.signal.aborted) return;
        content.textContent = "Request evidence unavailable. The session may have ended. ";
        const retry = document.createElement("button"); retry.textContent = "Retry"; retry.onclick = () => { void run(); }; content.append(retry);
      }
    };
    void run();
  }
}
