type Entry = { name: string; path: string; kind: string; size: number; accessible: boolean };

export class WorkspaceView {
  private tree: HTMLElement;
  private crumbs: HTMLElement;
  private status: HTMLElement;
  private content: HTMLElement;
  private title: HTMLElement;
  private meta: HTMLElement;
  private more: HTMLButtonElement;
  private controller?: AbortController;
  private fileController?: AbortController;
  private path = "";
  private cursor: string | null = null;
  private loaded = false;
  private selected: string | null = null;

  constructor(prefix = "workspace", private api = "/api/workspace", private rootLabel = "/workspace") {
    this.tree = document.querySelector<HTMLElement>(`#${prefix}-files`)!;
    this.crumbs = document.querySelector<HTMLElement>(`#${prefix}-breadcrumbs`)!;
    this.status = document.querySelector<HTMLElement>(`#${prefix}-status`)!;
    this.content = document.querySelector<HTMLElement>(`#${prefix}-file-content`)!;
    this.title = document.querySelector<HTMLElement>(`#${prefix}-file-title`)!;
    this.meta = document.querySelector<HTMLElement>(`#${prefix}-file-meta`)!;
    this.more = document.querySelector<HTMLButtonElement>(`#${prefix}-more`)!;
    document.querySelector<HTMLButtonElement>(`#${prefix}-refresh`)!.onclick = () => {
      const selected = this.selected;
      const path = this.path;
      void this.load(path).then(() => {
        if (selected && this.loaded && this.path === path && !this.selected) void this.read(selected);
      });
    };
    this.more.onclick = () => { void this.load(this.path, true); };
  }

  show(): void { if (!this.loaded) void this.load(this.path); }

  private clearFile(): void {
    this.title.textContent = "Select a file"; this.meta.textContent = ""; this.content.textContent = "";
  }

  private async request(url: string, signal: AbortSignal) {
    const response = await fetch(url, { signal, cache: "no-store" });
    if (!response.ok) {
      let message = `${this.rootLabel} unavailable. Refresh or restart the server after upgrading.`;
      try { const error = await response.json(); if (typeof error.detail === "string" && error.detail !== "Not Found") message = error.detail; } catch { /* safe fallback */ }
      throw new Error(message);
    }
    return response.json();
  }

  private breadcrumbs(): void {
    this.crumbs.replaceChildren();
    const add = (label: string, path: string) => {
      const button = document.createElement("button"); button.type = "button"; button.textContent = label;
      if (path === this.path) button.setAttribute("aria-current", "location");
      button.onclick = () => { void this.load(path); }; this.crumbs.append(button);
    };
    add(this.rootLabel, "");
    let prefix = "";
    for (const part of this.path.split("/").filter(Boolean)) {
      prefix = prefix ? `${prefix}/${part}` : part; add(part, prefix);
    }
  }

  private async load(path: string, append = false): Promise<void> {
    this.controller?.abort();
    const controller = new AbortController(); this.controller = controller;
    if (!append) {
      this.fileController?.abort(); this.clearFile(); this.selected = null;
      this.path = path; this.tree.replaceChildren(); this.cursor = null; this.loaded = false;
      this.breadcrumbs();
    }
    this.more.disabled = true; this.status.textContent = "Loading folder…";
    try {
      const params = new URLSearchParams({ path, ...(append && this.cursor ? { after: this.cursor } : {}) });
      const result = await this.request(`${this.api}?${params}`, controller.signal);
      if (controller.signal.aborted) return;
      for (const entry of result.entries as Entry[]) {
        const li = document.createElement("li"), button = document.createElement("button"), detail = document.createElement("small");
        button.type = "button"; button.textContent = entry.name + (entry.kind === "directory" ? "/" : "");
        button.dataset.path = entry.path; button.disabled = !entry.accessible;
        button.onclick = () => { if (entry.kind === "directory") void this.load(entry.path); else void this.read(entry.path); };
        detail.textContent = entry.accessible ? (entry.kind === "directory" ? "Folder" : `${entry.size.toLocaleString()} bytes`)
          : `${entry.kind} · preview unavailable`;
        li.append(button, detail); this.tree.append(li);
      }
      this.loaded = true; this.cursor = result.next_cursor;
      this.more.hidden = !this.cursor;
      this.status.textContent = this.tree.children.length ? `${this.tree.children.length} entries shown${this.cursor ? " · more available" : ""}` : "This folder is empty.";
    } catch (error) {
      if (!controller.signal.aborted) { this.more.hidden = true; this.status.textContent = error instanceof Error ? error.message : "Folder unavailable."; }
    } finally { if (!controller.signal.aborted) this.more.disabled = false; }
  }

  private async read(path: string): Promise<void> {
    this.fileController?.abort(); const controller = new AbortController(); this.fileController = controller;
    this.selected = path; this.clearFile(); this.title.textContent = `${this.rootLabel}/${path}`; this.meta.textContent = "Loading text…";
    for (const button of this.tree.querySelectorAll<HTMLButtonElement>("button")) {
      if (button.dataset.path === path) button.setAttribute("aria-current", "true"); else button.removeAttribute("aria-current");
    }
    try {
      const file = await this.request(`${this.api}/file?path=${encodeURIComponent(path)}`, controller.signal);
      if (controller.signal.aborted) return;
      this.content.textContent = file.content;
      this.meta.textContent = `${file.size.toLocaleString()} bytes · Modified ${new Date(file.modified_at * 1000).toLocaleString()} · Read-only UTF-8 text`;
    } catch (error) {
      if (!controller.signal.aborted) this.meta.textContent = error instanceof Error ? error.message : "File unavailable.";
    }
  }
}
