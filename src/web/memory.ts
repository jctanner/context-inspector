/** Read-only memory snapshots. Never render captured Markdown as HTML. */
type MemoryFile = { path: string; size: number; modified_at: number };

export class MemoryView {
  private panel = document.querySelector<HTMLElement>("#memory-section")!;
  private tree = document.querySelector<HTMLElement>("#memory-tree")!;
  private status = document.querySelector<HTMLElement>("#memory-status")!;
  private content = document.querySelector<HTMLElement>("#memory-content")!;
  private metadata = document.querySelector<HTMLElement>("#memory-file-meta")!;
  private title = document.querySelector<HTMLElement>("#memory-file-title")!;
  private refresh = document.querySelector<HTMLButtonElement>("#memory-refresh")!;
  private controller?: AbortController;
  private fileController?: AbortController;
  private owner: string | null = null;
  private selected: string | null = null;
  private loaded = false;

  constructor(private session: () => string | null) {
    this.refresh.onclick = () => { void this.load(); };
  }

  show(): void { if (!this.loaded || this.owner !== this.session()) void this.load(); }

  sessionChanged(): void {
    this.controller?.abort(); this.fileController?.abort(); this.loaded = false;
    this.owner = this.session(); this.selected = null; this.tree.replaceChildren(); this.clearFile();
    this.status.textContent = "Open Memory to load files.";
    if (!this.panel.hidden) void this.load();
  }

  private clearFile(): void {
    this.title.textContent = "Select a memory file"; this.metadata.textContent = ""; this.content.textContent = "";
  }

  private async request(url: string, signal: AbortSignal) {
    const response = await fetch(url, { cache: "no-store", signal });
    if (!response.ok) {
      let message = response.status === 404 ? "Memory unavailable. The session may have ended, or the backend needs restarting after an upgrade." : "Memory unavailable. Try Refresh.";
      try { const error = await response.json(); if (typeof error.detail === "string" && error.detail !== "Not Found") message = error.detail; } catch { /* Generic safe error. */ }
      throw new Error(message);
    }
    return response.json();
  }

  private async load(): Promise<void> {
    this.controller?.abort(); this.fileController?.abort(); this.loaded = false;
    const controller = new AbortController(); this.controller = controller;
    const owner = this.session();
    if (owner !== this.owner) this.selected = null;
    this.owner = owner; this.tree.replaceChildren(); this.clearFile();
    if (!owner) { this.status.textContent = "No active Claude session. Start Claude to browse its persistent memory mirror."; return; }
    this.status.textContent = "Loading memory files…";
    try {
      const result = await this.request(`/api/sessions/${encodeURIComponent(owner)}/memory`, controller.signal);
      if (controller.signal.aborted || owner !== this.session()) return;
      const files = result.files as MemoryFile[];
      this.loaded = true;
      this.status.textContent = files.length ? `${files.length} memory file${files.length === 1 ? "" : "s"}${result.truncated ? " · listing limit reached" : ""} · ${result.source}`
        : "No supported memory files found in the project-local mirror.";
      const root = document.createElement("ul"); this.tree.append(root);
      const folders = new Map<string, HTMLUListElement>([["", root]]);
      for (const file of files) {
        const parts = file.path.split("/"); let parent = root, prefix = "";
        for (const part of parts.slice(0, -1)) {
          prefix += `${part}/`;
          if (!folders.has(prefix)) {
            const li = document.createElement("li"), details = document.createElement("details"), summary = document.createElement("summary"), list = document.createElement("ul");
            summary.textContent = part; details.open = true; details.append(summary, list); li.append(details); parent.append(li); folders.set(prefix, list);
          }
          parent = folders.get(prefix)!;
        }
        const li = document.createElement("li"), button = document.createElement("button");
        button.type = "button"; button.textContent = parts.at(-1)!; button.title = file.path; button.dataset.path = file.path;
        button.onclick = () => { void this.read(file.path); }; li.append(button); parent.append(li);
      }
      if (this.selected && files.some(file => file.path === this.selected)) await this.read(this.selected);
      else this.selected = null;
    } catch (error) {
      if (!controller.signal.aborted) this.status.textContent = error instanceof Error ? error.message : "Memory unavailable.";
    }
  }

  private async read(path: string): Promise<void> {
    this.fileController?.abort(); const controller = new AbortController(); this.fileController = controller;
    const owner = this.owner; if (!owner) return;
    this.selected = path; this.clearFile(); this.title.textContent = `~/.claude/${path}`;
    this.metadata.textContent = "Loading Markdown source…";
    for (const button of this.tree.querySelectorAll<HTMLButtonElement>("button[data-path]")) {
      if (button.dataset.path === path) button.setAttribute("aria-current", "true"); else button.removeAttribute("aria-current");
    }
    try {
      const file = await this.request(`/api/sessions/${encodeURIComponent(owner)}/memory/file?path=${encodeURIComponent(path)}`, controller.signal);
      if (controller.signal.aborted || owner !== this.session()) return;
      this.metadata.textContent = `${file.size.toLocaleString()} bytes · Modified ${new Date(file.modified_at * 1000).toLocaleString()} · Read-only Markdown source`;
      this.content.textContent = file.content;
    } catch (error) {
      if (!controller.signal.aborted) this.metadata.textContent = error instanceof Error ? error.message : "Memory file unavailable.";
    }
  }
}
