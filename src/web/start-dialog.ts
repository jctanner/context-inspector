export type LaunchSelection = { harness: string; auth_mode: string; model: string };
type Profile = { harness: string; auth_mode: string; label: string; available: boolean; unavailable_reason: string | null; models: string[] };

export class StartDialog {
  private dialog = document.querySelector<HTMLDialogElement>("#start-dialog")!;
  private form = document.querySelector<HTMLFormElement>("#start-dialog-form")!;
  private harness = document.querySelector<HTMLSelectElement>("#start-harness")!;
  private auth = document.querySelector<HTMLSelectElement>("#start-auth")!;
  private model = document.querySelector<HTMLSelectElement>("#start-model")!;
  private confirm = document.querySelector<HTMLButtonElement>("#start-confirm")!;
  private cancel = document.querySelector<HTMLButtonElement>("#start-cancel")!;
  private status = document.querySelector<HTMLElement>("#start-dialog-status")!;
  private pending = false;
  private profiles: Profile[] = [];
  private generation = 0;

  constructor(start: (selection: LaunchSelection) => Promise<string | null>) {
    this.cancel.onclick = () => { this.generation++; this.dialog.close(); };
    this.dialog.addEventListener("cancel", event => { if (this.pending) event.preventDefault(); else this.generation++; });
    this.harness.onchange = () => this.updateAuth();
    this.auth.onchange = () => this.updateModels();
    this.form.addEventListener("submit", async event => {
      event.preventDefault();
      if (this.pending || !this.selected()?.available || !this.selected()?.models.includes(this.model.value)) return;
      this.pending = true;
      this.harness.disabled = this.auth.disabled = this.model.disabled = this.confirm.disabled = this.cancel.disabled = true;
      this.status.textContent = `Starting ${this.harness.value === "codex" ? "Codex" : "Claude"}…`;
      try {
        const error = await start({ harness: this.harness.value, auth_mode: this.auth.value, model: this.model.value });
        if (error === null) this.dialog.close();
        else this.status.textContent = error;
      } catch {
        this.status.textContent = "Could not start session. Please try again.";
      } finally {
        this.pending = false;
        this.harness.disabled = this.auth.disabled = this.cancel.disabled = false;
        this.model.disabled = this.confirm.disabled = !this.selected()?.available;
      }
    });
  }

  private selected(): Profile | undefined {
    return this.profiles.find(p => p.harness === this.harness.value && p.auth_mode === this.auth.value);
  }

  private options(select: HTMLSelectElement, values: Array<[string, string]>): void {
    select.replaceChildren(...values.map(([value, label]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = label; return option;
    }));
  }

  private updateAuth(): void {
    this.options(this.auth, this.profiles.filter(p => p.harness === this.harness.value).map(p => [p.auth_mode, p.auth_mode === "vertex" ? "Vertex" : "OAuth account login"]));
    this.updateModels();
  }

  private updateModels(): void {
    const profile = this.selected();
    this.options(this.model, (profile?.models ?? []).map(model => [model, model]));
    this.model.disabled = this.confirm.disabled = !profile?.available || !profile.models.length;
    this.status.textContent = profile?.unavailable_reason ?? "";
  }

  async show(): Promise<void> {
    if (this.dialog.open) return;
    const generation = ++this.generation;
    this.profiles = [];
    this.harness.disabled = this.auth.disabled = this.model.disabled = this.confirm.disabled = true;
    this.status.textContent = "Loading launch options…";
    this.dialog.showModal();
    try {
      const response = await fetch("/api/profiles", { cache: "no-store" });
      if (!response.ok) throw new Error();
      const catalog = await response.json() as { profiles: Profile[]; default: LaunchSelection };
      if (generation !== this.generation || !this.dialog.open) return;
      this.profiles = catalog.profiles;
      this.options(this.harness, [...new Set(this.profiles.map(p => p.harness))].map(h => [h, h === "codex" ? "Codex" : "Claude"]));
      this.harness.value = catalog.default.harness;
      this.updateAuth(); this.auth.value = catalog.default.auth_mode; this.updateModels();
      this.model.value = catalog.default.model;
      this.harness.disabled = this.auth.disabled = false;
      this.model.focus();
    } catch {
      if (generation === this.generation) this.status.textContent = "Launch options could not be loaded. Close and try again.";
    }
  }
}
