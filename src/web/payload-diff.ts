import { element } from "./readable";
import { addPayloadOutline } from "./payload-outline";

type RequestEvidence = {
  predecessor_flow_id: string | null;
  predecessor_basis: string;
  predecessor_confidence: string;
  exact_request: Record<string, unknown>;
};

function body(request: RequestEvidence): unknown {
  const value = request.exact_request.body as { decoded?: { kind?: string; value?: unknown } } | undefined;
  if (!value?.decoded || !Object.hasOwn(value.decoded, "value")) throw new Error("Decoded request payload unavailable");
  return value.decoded.value;
}

export function addPayloadDiff(parent: HTMLElement, structured: HTMLElement, request: RequestEvidence, session: string, signal: AbortSignal): void {
  const controls = element("div", "payload-controls", "");
  const toggle = document.createElement("button"); toggle.type = "button"; toggle.className = "payload-toggle secondary-button";
  toggle.textContent = "Full payload diff"; toggle.setAttribute("aria-pressed", "false");
  controls.append(toggle);
  const view = element("section", "payload-view", ""); view.hidden = true;
  parent.prepend(controls); parent.append(view);
  let loaded = false, loading = false;
  let worker: Worker | undefined;
  signal.addEventListener("abort", () => worker?.terminate(), { once: true });
  const load = async () => {
    if (loaded || loading || signal.aborted) return;
    loading = true; view.textContent = "Loading complete payload comparison…";
    try {
      const after = body(request);
      let before: unknown;
      if (request.predecessor_flow_id !== null) {
        const response = await fetch(`/api/sessions/${encodeURIComponent(session)}/context-details/${encodeURIComponent(request.predecessor_flow_id)}/request`, { cache: "no-store", signal });
        if (!response.ok) throw new Error("Recorded comparison baseline is unavailable; no substitute baseline was used");
        before = body(await response.json());
      }
      if (signal.aborted) return;
      worker = new Worker(new URL("./payload-diff.worker.ts", import.meta.url), { type: "module" });
      worker.onerror = () => { worker?.terminate(); loading = false; view.textContent = "Could not compute payload diff. Switch back and retry."; };
      worker.onmessage = async event => {
        worker?.terminate();
        if (signal.aborted) return;
        const lines = event.data.lines as { kind: "same" | "add" | "remove"; text: string }[];
        view.replaceChildren(element("p", "payload-provenance", `Complete decoded JSON body, pretty-printed (not original wire formatting). ${request.predecessor_flow_id === null ? "No predecessor: all lines are additions." : `Baseline flow ${request.predecessor_flow_id} · ${request.predecessor_basis} · ${request.predecessor_confidence} confidence.`}`));
        if (event.data.fallback) view.append(element("p", "payload-provenance", "Large change: showing the changed region as a complete replacement; no lines omitted."));
        const additions = lines.filter(line => line.kind === "add").length, removals = lines.filter(line => line.kind === "remove").length;
        const navigation = element("div", "payload-navigation", "");
        navigation.append(element("span", "", additions || removals ? `+${additions} lines · −${removals} lines` : "Payloads identical"));
        const changes: HTMLElement[] = [];
        let outline: ReturnType<typeof addPayloadOutline> | undefined;
        const changeButtons: HTMLButtonElement[] = [];
        let selected = -1;
        for (const [label, direction] of [["Previous change", -1], ["Next change", 1]] as const) {
          const button = document.createElement("button"); button.type = "button"; button.className = "secondary-button"; button.textContent = label;
          button.disabled = true;
          changeButtons.push(button);
          button.onclick = () => {
            if (!changes.length || !outline) return;
            selected = selected === -1 ? (direction === 1 ? 0 : changes.length - 1)
              : (selected + direction + changes.length) % changes.length;
            outline.selectRow(changes[selected]);
          };
          navigation.append(button);
        }
        view.append(navigation);
        const table = document.createElement("table"); table.className = "payload-diff"; table.setAttribute("aria-label", "Full request payload unified diff");
        const head = document.createElement("thead"); const labels = document.createElement("tr");
        for (const name of ["Before", "After", "Change", "Payload"]) { const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = name; labels.append(cell); }
        head.append(labels); table.append(head);
        const layout = element("div", "payload-layout", "");
        const rows = document.createElement("tbody"); table.append(rows); layout.append(table); view.append(layout);
        const beforeRows = new Map<number, HTMLElement>(), afterRows = new Map<number, HTMLElement>();
        let oldLine = 0, newLine = 0;
        for (let offset = 0; offset < lines.length; offset += 300) {
          if (signal.aborted) return;
          const fragment = document.createDocumentFragment();
          for (let i = offset; i < Math.min(offset + 300, lines.length); i++) {
            const line = lines[i], row = document.createElement("tr"); row.className = `payload-${line.kind}`;
            if (line.kind !== "add") oldLine++;
            if (line.kind !== "remove") newLine++;
            if (line.kind !== "add") beforeRows.set(oldLine, row);
            if (line.kind !== "remove") afterRows.set(newLine, row);
            row.append(element("td", "line-number", line.kind === "add" ? "" : String(oldLine)), element("td", "line-number", line.kind === "remove" ? "" : String(newLine)), element("td", "line-sign", line.kind === "add" ? "+" : line.kind === "remove" ? "−" : " "));
            const content = document.createElement("td"); content.append(element("pre", "", line.text)); row.append(content); fragment.append(row);
            if (line.kind !== "same" && (i === 0 || lines[i - 1].kind === "same")) changes.push(row);
          }
          rows.append(fragment);
          await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
        }
        if (signal.aborted) return;
        outline = addPayloadOutline(layout, event.data.beforeOutline, event.data.afterOutline, beforeRows, afterRows);
        for (const button of changeButtons) button.disabled = !changes.length;
        loaded = true; loading = false;
      };
      worker.postMessage({ before, after });
    } catch (error) {
      loading = false;
      if (!signal.aborted) view.textContent = `${error instanceof Error ? error.message : "Payload comparison unavailable"}. Switch back and retry.`;
    }
  };
  toggle.onclick = () => {
    const show = view.hidden; view.hidden = !show; structured.hidden = show;
    toggle.textContent = show ? "Block inspection" : "Full payload diff"; toggle.setAttribute("aria-pressed", String(show));
    if (show) void load();
  };
  // Reuse the normal view transition so visibility, accessible state and lazy
  // baseline loading remain consistent. Only opening a request tab starts this.
  toggle.click();
}
