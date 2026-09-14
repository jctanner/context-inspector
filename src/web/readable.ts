/** Text-only presentation: captured content never becomes HTML. */
export function element(tag: string, className: string, text: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

export function disclosure(parent: HTMLElement, title: string, className = ""): HTMLDetailsElement {
  const node = document.createElement("details");
  node.className = `disclosure ${className}`;
  node.append(element("summary", "", title));
  parent.append(node);
  return node;
}

export function readableValue(parent: HTMLElement, value: unknown, collapseLong = true): void {
  if (typeof value === "string") {
    if (collapseLong && value.length > 800) {
      parent.append(element("div", "readable-text content-preview", `${value.slice(0,240)}…`));
      const full = disclosure(parent, `Read full content (${value.length.toLocaleString()} characters)`);
      full.append(element("div", "readable-text", value));
    } else parent.append(element("div", "readable-text", value));
  } else if (Array.isArray(value)) {
    value.forEach(part => readableValue(parent, part, collapseLong));
  } else if (value && typeof value === "object") {
    const block = value as Record<string, unknown>;
    if (typeof block.text === "string") readableValue(parent, block.text, collapseLong);
    else if (typeof block.thinking === "string") readableValue(parent, block.thinking, collapseLong);
    else if (block.type === "tool_result") {
      parent.append(element("p", "block-label", `Tool result${block.is_error ? " · error" : ""}`));
      readableValue(parent, block.content);
    } else if (typeof block.name === "string") {
      parent.append(element("p", "block-label", block.name));
      if (typeof block.description === "string") readableValue(parent, block.description);
      if (block.input !== undefined) readableValue(parent, block.input);
      if (block.input_schema !== undefined) readableValue(disclosure(parent, "Input schema"), block.input_schema);
    } else {
      parent.append(element("pre", "structured-content", JSON.stringify(value, null, 2)));
    }
  } else if (value !== undefined && value !== null) {
    parent.append(element("div", "readable-text", String(value)));
  }
}

export function readableBlock(parent: HTMLElement, block: Record<string, unknown> | null, label: string): void {
  if (!block) return;
  const node = document.createElement("section");
  node.className = `block-content ${label.toLowerCase()}`;
  node.append(element("h4", "block-label", label));
  readableValue(node, block.value);
  parent.append(node);
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(",")}}`;
  return JSON.stringify(value) ?? "undefined";
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function readableChange(parent: HTMLElement, before: Record<string, unknown> | null, after: Record<string, unknown> | null): void {
  const oldValue = record(before?.value);
  const newValue = record(after?.value);
  const textKey = ["text", "thinking"].find(key => typeof oldValue?.[key] === "string" && typeof newValue?.[key] === "string");
  const unchangedText = textKey !== undefined && oldValue![textKey] === newValue![textKey];
  // Cache hints alter the wire value, not the tool call/result itself. Compare
  // every other field, including IDs and nested input, before calling it unchanged.
  const withoutCache = (value: Record<string, unknown>) => Object.fromEntries(Object.entries(value).filter(([key]) => key !== "cache_control"));
  const unchangedTool = oldValue && newValue
    && ["tool_use", "tool_result"].includes(String(oldValue.type))
    && canonical(withoutCache(oldValue)) === canonical(withoutCache(newValue));
  const toolLabel = oldValue?.type === "tool_result" ? "Tool result" : "Tool call";
  const keys = oldValue && newValue ? [...new Set([...Object.keys(oldValue), ...Object.keys(newValue)])]
    .filter(key => key !== textKey && canonical(oldValue[key]) !== canonical(newValue[key])) : [];
  const action = (key: string) => !Object.hasOwn(newValue!, key) ? "removed" : !Object.hasOwn(oldValue!, key) ? "added" : "changed";
  const fieldSummary = keys.map(key => `${key === "cache_control" ? "cache-control metadata" : key} ${action(key)}`).join(" · ");
  parent.append(element("p", "change-explanation", `${unchangedTool ? `${toolLabel} unchanged` : unchangedText ? "Text unchanged" : textKey ? "Text changed" : "Block value changed"}${fieldSummary ? ` · ${fieldSummary}` : ""}`));
  if (keys.length) {
    const table = document.createElement("table");
    table.className = "field-changes";
    const caption = document.createElement("caption");
    caption.textContent = "Changed block fields";
    table.append(caption);
    const head = document.createElement("thead");
    const labels = document.createElement("tr");
    for (const name of ["Field", "Before", "After"]) {
      const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = name; labels.append(cell);
    }
    head.append(labels); table.append(head);
    const body = document.createElement("tbody");
    for (const key of keys) {
      const row = document.createElement("tr");
      const label = document.createElement("th"); label.scope = "row"; label.textContent = `${key} (${action(key)})`; row.append(label);
      for (const value of [oldValue!, newValue!]) {
        const cell = document.createElement("td");
        cell.append(element("pre", "", Object.hasOwn(value, key) ? JSON.stringify(value[key], null, 2) : "Not present"));
        row.append(cell);
      }
      body.append(row);
    }
    table.append(body); parent.append(table);
  }
  if (unchangedTool) {
    const shared = disclosure(parent, `Unchanged ${toolLabel.toLowerCase()}`, "unchanged-tool");
    readableValue(shared, withoutCache(oldValue!));
  } else if (unchangedText) {
    const shared = disclosure(parent, "Unchanged text", "unchanged-text");
    readableValue(shared, oldValue![textKey!]);
  } else {
    const comparison = document.createElement("div");
    comparison.className = "before-after";
    readableBlock(comparison, before, "Before");
    readableBlock(comparison, after, "After");
    parent.append(comparison);
  }
}
