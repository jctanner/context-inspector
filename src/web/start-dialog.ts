export class StartDialog {
  private dialog = document.querySelector<HTMLDialogElement>("#start-dialog")!;
  private form = document.querySelector<HTMLFormElement>("#start-dialog-form")!;
  private model = document.querySelector<HTMLSelectElement>("#start-model")!;
  private confirm = document.querySelector<HTMLButtonElement>("#start-confirm")!;
  private cancel = document.querySelector<HTMLButtonElement>("#start-cancel")!;
  private status = document.querySelector<HTMLElement>("#start-dialog-status")!;
  private pending = false;

  constructor(start: (model: string) => Promise<string | null>) {
    this.cancel.onclick = () => { this.dialog.close(); };
    this.dialog.addEventListener("cancel", event => { if (this.pending) event.preventDefault(); });
    this.form.addEventListener("submit", async event => {
      event.preventDefault();
      if (this.pending) return;
      this.pending = true;
      this.model.disabled = this.confirm.disabled = this.cancel.disabled = true;
      this.status.textContent = "Starting Claude…";
      try {
        const error = await start(this.model.value);
        if (error === null) this.dialog.close();
        else this.status.textContent = error;
      } catch {
        this.status.textContent = "Could not start Claude. Please try again.";
      } finally {
        this.pending = false;
        this.model.disabled = this.confirm.disabled = this.cancel.disabled = false;
      }
    });
  }

  show(): void {
    if (this.dialog.open) return;
    this.model.value = "claude-haiku-4-5";
    this.status.textContent = "";
    this.dialog.showModal();
    this.model.focus();
  }
}
