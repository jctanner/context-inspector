import { element } from "./readable";
import { addPayloadOutline } from "./payload-outline";
import { renderSplitPayload } from "./payload-split";

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
  addPayloadView(parent, structured, signal, {
    payloadLabel: "Full payload diff", structuredLabel: "Block inspection", tableLabel: "Full request payload unified diff",
    load: async () => {
      const after = body(request);
      let before: unknown;
      if (request.predecessor_flow_id !== null) {
        const response = await fetch(`/api/sessions/${encodeURIComponent(session)}/context-details/${encodeURIComponent(request.predecessor_flow_id)}/request`, { cache: "no-store", signal });
        if (!response.ok) throw new Error("Recorded comparison baseline is unavailable; no substitute baseline was used");
        before = body(await response.json());
      }
      return { before, after, provenance: `Complete decoded JSON body, pretty-printed (not original wire formatting). ${request.predecessor_flow_id === null ? "No predecessor: all lines are additions." : `Baseline flow ${request.predecessor_flow_id} · ${request.predecessor_basis} · ${request.predecessor_confidence} confidence.`}` };
    },
  });
}

type PayloadViewOptions = {
  payloadLabel: string; structuredLabel: string; tableLabel: string; rootLabel?: string;
  load: () => Promise<{ before?: unknown; after: unknown; provenance: string; fullOnly?: boolean }>;
};

export function addPayloadView(parent: HTMLElement, structured: HTMLElement, signal: AbortSignal, options: PayloadViewOptions): void {
  const controls = element("div", "payload-controls", "");
  const toggle = document.createElement("button"); toggle.type = "button"; toggle.className = "payload-toggle secondary-button";
  toggle.textContent = options.payloadLabel; toggle.setAttribute("aria-pressed", "false");
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
      const { before, after, provenance, fullOnly } = await options.load();
      if (signal.aborted) return;
      worker = new Worker(new URL("./payload-diff.worker.ts", import.meta.url), { type: "module" });
      worker.onerror = () => { worker?.terminate(); loading = false; view.textContent = "Could not compute payload diff. Switch back and retry."; };
      worker.onmessage = async event => {
        worker?.terminate();
        if (signal.aborted) return;
        if (options.rootLabel) {
          for (const node of [event.data.beforeOutline, event.data.afterOutline]) {
            if (node) node.label = node.label.replace(/^Request payload/, options.rootLabel);
          }
        }
        const lines = event.data.lines as { kind: "same" | "add" | "remove"; text: string }[];
        view.replaceChildren(element("p", "payload-provenance", provenance));
        if (event.data.fallback) view.append(element("p", "payload-provenance", "Large change: showing the changed region as a complete replacement; no lines omitted."));
        const additions = lines.filter(line => line.kind === "add").length, removals = lines.filter(line => line.kind === "remove").length;
        const navigation = element("div", "payload-navigation", "");
        navigation.append(element("span", "", fullOnly ? "Full payload · no comparison selected" : additions || removals ? `+${additions} lines · −${removals} lines` : "Payloads identical"));
        let changes: HTMLElement[] = [];
        const changeIndices: number[] = [];
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
        const layouts = element("div", "payload-layout-controls", "");
        layouts.setAttribute("role", "group"); layouts.setAttribute("aria-label", "Diff layout");
        const inlineButton = document.createElement("button"), splitButton = document.createElement("button");
        for (const [button, label] of [[inlineButton, "Inline"], [splitButton, "Side-by-side"]] as const) {
          button.type = "button"; button.className = "secondary-button"; button.textContent = label;
          button.setAttribute("aria-pressed", String(button === inlineButton)); button.disabled = true;
          layouts.append(button);
        }
        navigation.append(layouts);
        view.append(navigation);
        const table = document.createElement("table"); table.className = "payload-diff"; table.setAttribute("aria-label", options.tableLabel);
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
            if (line.kind !== "same" && (i === 0 || lines[i - 1].kind === "same")) { changes.push(row); changeIndices.push(i); }
          }
          rows.append(fragment);
          await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
        }
        if (signal.aborted) return;
        outline = addPayloadOutline(layout, event.data.beforeOutline, event.data.afterOutline, beforeRows, afterRows);
        const inline = { layout, outline, changes, beforeRows, afterRows };
        let split: typeof inline | undefined;
        let splitActive = false;
        const switchLayout = async (useSplit: boolean) => {
          if (useSplit === splitActive || signal.aborted) return;
          const location = outline?.getLocation();
          inlineButton.disabled = splitButton.disabled = true;
          if (useSplit && !split) {
            layouts.setAttribute("aria-busy", "true");
            const rendered = await renderSplitPayload(lines, signal);
            if (!rendered || signal.aborted) return;
            rendered.table.setAttribute("aria-label", `${options.tableLabel} side-by-side`);
            const splitLayout = element("div", "payload-layout", ""); splitLayout.hidden = true;
            splitLayout.append(rendered.table); view.append(splitLayout);
            split = { layout: splitLayout,
              outline: addPayloadOutline(splitLayout, event.data.beforeOutline, event.data.afterOutline, rendered.beforeRows, rendered.afterRows),
              changes: changeIndices.map(index => rendered.targets.get(index)!),
              beforeRows: rendered.beforeRows, afterRows: rendered.afterRows };
            layouts.removeAttribute("aria-busy");
          }
          const active = useSplit ? split! : inline;
          inline.layout.hidden = useSplit;
          if (split) split.layout.hidden = !useSplit;
          outline = active.outline; changes = active.changes; splitActive = useSplit;
          inlineButton.setAttribute("aria-pressed", String(!useSplit)); splitButton.setAttribute("aria-pressed", String(useSplit));
          inlineButton.disabled = splitButton.disabled = false;
          if (location?.line !== undefined) {
            const target = (location.side === "Before" ? active.beforeRows : active.afterRows).get(location.line);
            if (target) outline.selectRow(target, location.side);
          }
        };
        inlineButton.onclick = () => { void switchLayout(false); };
        splitButton.onclick = () => { void switchLayout(true); };
        inlineButton.disabled = splitButton.disabled = false;
        for (const button of changeButtons) button.disabled = !changes.length;
        loaded = true; loading = false;
      };
      worker.postMessage({ before: fullOnly ? after : before, after });
    } catch (error) {
      loading = false;
      if (!signal.aborted) view.textContent = `${error instanceof Error ? error.message : "Payload comparison unavailable"}. Switch back and retry.`;
    }
  };
  toggle.onclick = () => {
    const show = view.hidden; view.hidden = !show; structured.hidden = show;
    toggle.textContent = show ? options.structuredLabel : options.payloadLabel; toggle.setAttribute("aria-pressed", String(show));
    if (show) void load();
  };
  // Reuse the normal view transition so visibility, accessible state and lazy
  // baseline loading remain consistent. Only opening a request tab starts this.
  toggle.click();
}
