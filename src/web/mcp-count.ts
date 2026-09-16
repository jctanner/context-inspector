export function setupMcpCount(): void {
  const form = document.querySelector<HTMLFormElement>("#mcp-count-form")!;
  const input = document.querySelector<HTMLInputElement>("#mcp-count")!;
  const apply = document.querySelector<HTMLButtonElement>("#mcp-count-apply")!;
  const refresh = document.querySelector<HTMLButtonElement>("#mcp-count-refresh")!;
  const status = document.querySelector<HTMLElement>("#mcp-count-status")!;
  let revision: string | null = null;
  const busy = (value: boolean): void => {
    input.disabled = value;
    apply.disabled = value || revision === null;
    refresh.disabled = value;
  };
  async function load(save = false): Promise<void> {
    const value = input.value.trim();
    if (save && (!/^[0-9]+$/.test(value) || BigInt(value) <= 0n)) {
      status.textContent = "Enter a positive integer.";
      input.focus();
      return;
    }
    busy(true);
    status.textContent = save ? "Saving…" : "Loading MCP count…";
    try {
      const response = await fetch("/api/mcp-dump/count", save ? {
        method: "PUT", headers: { "Content-Type": "application/json", "X-Context-Inspector": "1" },
        body: JSON.stringify({ tool_count: value, revision }),
      } : { cache: "no-store" });
      if (!response.ok) {
        if (response.status === 404) throw new Error("Restart the server to enable this control.");
        const error = await response.json();
        throw new Error(typeof error.detail === "string" ? error.detail : "Could not save MCP count.");
      }
      const result = await response.json();
      revision = result.revision;
      input.value = result.tool_count ?? "";
      status.textContent = save
        ? `Saved ${input.value} tools. Claude reload is not confirmed.`
        : `Configured: ${result.tool_count ?? "invalid count"}. Not a live tool measurement.`;
    } catch (error) {
      if (!save) revision = null;
      status.textContent = error instanceof Error ? error.message : String(error);
    } finally { busy(false); }
  }
  form.addEventListener("submit", event => { event.preventDefault(); void load(true); });
  refresh.addEventListener("click", () => { void load(); });
  void load();
}
