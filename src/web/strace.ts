export function setupStrace(): void {
  const form = document.querySelector<HTMLFormElement>("#strace-search")!;
  const query = document.querySelector<HTMLInputElement>("#strace-query")!;
  const submit = document.querySelector<HTMLButtonElement>("#strace-submit")!;
  const status = document.querySelector<HTMLElement>("#strace-status")!;
  const results = document.querySelector<HTMLElement>("#strace-results")!;
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (!query.value || submit.disabled) return;
    submit.disabled = true;
    results.replaceChildren();
    status.textContent = "Searching trace files…";
    results.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(`/api/strace/search?${new URLSearchParams({ q: query.value })}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Trace search unavailable");
      const fragment = document.createDocumentFragment();
      for (const match of data.matches as { path: string; line: number; text: string }[]) {
        const row = document.createElement("li");
        const location = document.createElement("div");
        location.className = "strace-location";
        location.textContent = `${match.path}:${match.line}`;
        const text = document.createElement("pre");
        text.tabIndex = 0;
        text.textContent = match.text;
        row.append(location, text);
        fragment.append(row);
      }
      results.append(fragment);
      status.textContent = data.missing
        ? "No trace folder yet. Start a tracing-enabled Claude container to create logs."
        : `${data.partial ? "Partial search: " : ""}${data.matches.length} matching lines in ${data.files_scanned} files scanned (${(data.bytes_scanned / 1048576).toFixed(1)} MiB). ${data.warnings.join(". ")}${data.partial ? ". Results are incomplete." : ""}`;
    } catch (error) {
      status.textContent = `Search failed: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      submit.disabled = false;
      results.removeAttribute("aria-busy");
    }
  };
}
