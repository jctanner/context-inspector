export type PayloadNode = { label: string; path: string; line: number; endLine: number; children: PayloadNode[] };

// Parsed JSON has no omitted/undefined properties. Nonempty containers occupy
// one opening line, their child lines, and one closing line in JSON.stringify.
export function payloadOutline(value: unknown): PayloadNode | null {
  if (value === undefined) return null;
  let line = 1;
  const visit = (value: unknown, key: string, path: string): PayloadNode => {
    const container = value !== null && typeof value === "object";
    const entries = container ? Object.entries(value) : [];
    const record = container && !Array.isArray(value) ? value as Record<string, unknown> : {};
    const hint = [record.role, record.type, record.name].filter(v => typeof v === "string").join(" · ").slice(0, 80);
    const shape = Array.isArray(value) ? `[${entries.length}]` : container ? `{${entries.length}}` : value === null ? "null" : typeof value;
    const node: PayloadNode = { label: `${key} ${shape}${hint ? ` · ${hint}` : ""}`, path, line: line++, endLine: 0, children: [] };
    for (const [childKey, child] of entries) {
      node.children.push(visit(child, Array.isArray(value) ? `[${childKey}]` : childKey,
        `${path}/${childKey.replace(/~/g, "~0").replace(/\//g, "~1")}`));
    }
    if (entries.length) line++;
    node.endLine = line - 1;
    return node;
  };
  const root = visit(value, "$", "");
  const container = value !== null && typeof value === "object";
  const unit = Array.isArray(value) ? "item" : "field";
  const description = container ? `${root.children.length} ${unit}${root.children.length === 1 ? "" : "s"}`
    : value === null ? "null" : typeof value;
  root.label = `Request payload · ${description}`;
  return root;
}
