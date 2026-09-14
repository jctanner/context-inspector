import { element } from "./readable";

export type DiffLine = { kind: "same" | "add" | "remove"; text: string };

export async function renderSplitPayload(lines: DiffLine[], signal: AbortSignal) {
  const table = document.createElement("table"); table.className = "payload-diff payload-split";
  table.setAttribute("aria-label", "Full request payload side-by-side diff");
  const head = document.createElement("thead"), groups = document.createElement("tr"), heading = document.createElement("tr");
  for (const side of ["Before", "After"]) {
    const columns = document.createElement("colgroup");
    for (const kind of ["number", "sign", "content"]) {
      const column = document.createElement("col"); column.className = `split-column-${kind}`; columns.append(column);
    }
    table.append(columns);
    const group = document.createElement("th"); group.scope = "colgroup"; group.colSpan = 3; group.textContent = side; groups.append(group);
    for (const [label, name] of [["#", "line number"], ["+/−", "change"], ["Payload", "payload"]]) {
      const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = label;
      cell.setAttribute("aria-label", `${side} ${name}`); heading.append(cell);
    }
  }
  head.append(groups, heading); table.append(head);
  const body = document.createElement("tbody"); table.append(body);
  const beforeRows = new Map<number, HTMLElement>(), afterRows = new Map<number, HTMLElement>();
  const targets = new Map<number, HTMLElement>();
  let oldLine = 0, newLine = 0, rendered = 0;
  let fragment = document.createDocumentFragment();
  const append = (before: number | null, after: number | null) => {
    const row = document.createElement("tr");
    for (const [index, side] of [[before, "before"], [after, "after"]] as const) {
      const line = index === null ? null : lines[index];
      const number = line ? (side === "before" ? ++oldLine : ++newLine) : null;
      const kind = line ? `payload-${line.kind}` : "payload-empty";
      const count = element("td", `line-number ${kind}`, number === null ? "" : String(number));
      const sign = element("td", `line-sign ${kind}`, line?.kind === "remove" ? "−" : line?.kind === "add" ? "+" : "");
      const content = element("td", `split-content split-${side} ${kind}`, "");
      if (line) {
        content.append(element("pre", "", line.text));
        (side === "before" ? beforeRows : afterRows).set(number!, content);
        targets.set(index!, content);
      }
      row.append(count, sign, content);
    }
    fragment.append(row); rendered++;
  };
  for (let i = 0; i < lines.length;) {
    if (signal.aborted) return null;
    if (lines[i].kind === "same") { append(i, i); i++; }
    else {
      const removed: number[] = [], added: number[] = [];
      while (i < lines.length && lines[i].kind !== "same") {
        (lines[i].kind === "remove" ? removed : added).push(i++);
      }
      for (let j = 0; j < Math.max(removed.length, added.length); j++) {
        if (signal.aborted) return null;
        append(removed[j] ?? null, added[j] ?? null);
        if (rendered % 300 === 0) {
          body.append(fragment); fragment = document.createDocumentFragment();
          await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
        }
      }
    }
    if (rendered % 300 === 0) {
      body.append(fragment); fragment = document.createDocumentFragment();
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    }
  }
  body.append(fragment);
  return { table, beforeRows, afterRows, targets };
}
