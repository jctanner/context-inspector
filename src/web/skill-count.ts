export function setupSkillCount(): void {
  const form = document.querySelector<HTMLFormElement>("#skill-count-form")!;
  const input = document.querySelector<HTMLInputElement>("#skill-count")!;
  const apply = document.querySelector<HTMLButtonElement>("#skill-count-apply")!;
  const refresh = document.querySelector<HTMLButtonElement>("#skill-count-refresh")!;
  const status = document.querySelector<HTMLElement>("#skill-count-status")!;
  let revision: string | null = null;
  let running = false;
  let timer: number | undefined;
  async function load(save = false): Promise<void> {
    const value = input.value.trim();
    if (save && (!/^[0-9]+$/.test(value) || BigInt(value) <= 0n)) {
      status.textContent = "Enter a positive integer.";
      input.focus();
      return;
    }
    window.clearTimeout(timer);
    input.disabled = apply.disabled = refresh.disabled = true;
    status.textContent = save ? "Starting skill update…" : "Reading generated skills…";
    try {
      const response = await fetch("/api/skill-dump/count", save ? {
        method: "PUT", headers: { "Content-Type": "application/json", "X-Context-Inspector": "1" },
        body: JSON.stringify({ skill_count: value, revision }),
      } : { cache: "no-store" });
      if (!response.ok) {
        if (response.status === 404) throw new Error("Restart the server to enable skill control.");
        const error = await response.json();
        throw new Error(typeof error.detail === "string" ? error.detail : "Could not update skills.");
      }
      const result = await response.json();
      revision = result.revision;
      running = result.running;
      input.value = running ? result.target_count : result.skill_count;
      status.textContent = result.error || (running
        ? `Updating: ${result.skill_count} / ${result.target_count} files.`
        : `On disk: ${result.skill_count}. Claude registry not confirmed.`);
      if (running) timer = window.setTimeout(() => { void load(); }, 1000);
    } catch (error) {
      if (!save) revision = null;
      status.textContent = error instanceof Error ? error.message : String(error);
    } finally {
      input.disabled = running;
      apply.disabled = running || revision === null;
      refresh.disabled = false;
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); void load(true); });
  refresh.addEventListener("click", () => { void load(); });
  window.addEventListener("pagehide", () => { window.clearTimeout(timer); });
  void load();
}
