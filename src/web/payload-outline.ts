import { element } from "./readable";
import type { PayloadNode } from "./payload-outline-model";

export function addPayloadOutline(layout: HTMLElement, before: PayloadNode | null, after: PayloadNode,
  beforeRows: Map<number, HTMLElement>, afterRows: Map<number, HTMLElement>) {
  const outline = element("nav", "payload-outline", "");
  outline.setAttribute("aria-label", "Payload outline");
  const heading = element("h3", "", "Payload outline");
  const label = element("label", "payload-outline-side", "Payload side ");
  const side = document.createElement("select");
  for (const name of ["After", "Before"]) {
    const option = document.createElement("option"); option.value = name; option.textContent = name;
    option.disabled = name === "Before" && before === null; side.append(option);
  }
  label.append(side);
  const tree = element("div", "payload-outline-tree", "");
  outline.append(heading, label, tree); layout.prepend(outline);
  let selected: HTMLElement | undefined, target: HTMLElement | undefined;
  const buttons = new Map<PayloadNode, HTMLButtonElement>();
  const revealChildren = new Map<PayloadNode, (index: number) => void>();
  const oldLines = new Map([...beforeRows].map(([line, row]) => [row, line]));
  const newLines = new Map([...afterRows].map(([line, row]) => [row, line]));
  const select = (button: HTMLElement, row: HTMLElement | undefined) => {
    selected?.removeAttribute("aria-current"); target?.classList.remove("payload-target");
    selected = button; selected.setAttribute("aria-current", "location");
    target = row; target?.classList.add("payload-target");
  };
  const render = () => {
    selected?.removeAttribute("aria-current"); target?.classList.remove("payload-target");
    selected = target = undefined;
    tree.replaceChildren();
    buttons.clear(); revealChildren.clear();
    const rows = side.value === "After" ? afterRows : beforeRows;
    const root = side.value === "After" ? after : before;
    if (!root) return;
    const jump = (node: PayloadNode) => {
      const button = document.createElement("button"); button.type = "button";
      button.className = "payload-outline-link"; button.textContent = node.label;
      button.title = `${side.value} JSON Pointer: ${node.path || '(root)'} · line ${node.line}`;
      button.dataset.path = node.path;
      buttons.set(node, button);
      button.onclick = event => {
        event.preventDefault(); event.stopPropagation();
        select(button, rows.get(node.line));
        target?.scrollIntoView({ block: "center", inline: "nearest" });
      };
      return button;
    };
    const children = (parent: HTMLElement, owner: PayloadNode) => {
      const nodes = owner.children;
      const list = document.createElement("ul"); parent.append(list);
      let offset = 0;
      const more = document.createElement("button"); more.type = "button"; more.className = "secondary-button";
      const batch = () => {
        more.remove();
        const end = Math.min(offset + 100, nodes.length);
        for (; offset < end; offset++) {
          const node = nodes[offset], item = document.createElement("li");
          if (node.children.length) {
            const branch = document.createElement("details"), summary = document.createElement("summary");
            summary.append(jump(node));
            branch.append(summary);
            let populated = false;
            const populate = () => { if (!populated) { populated = true; children(branch, node); } };
            revealChildren.set(node, index => {
              branch.open = true; populate(); revealChildren.get(node)!(index);
            });
            branch.ontoggle = () => { if (branch.open) populate(); };
            item.append(branch);
          } else item.append(jump(node));
          list.append(item);
        }
        if (offset < nodes.length) { more.textContent = `Show more (${nodes.length - offset} remaining)`; parent.append(more); }
      };
      more.onclick = batch; batch();
      revealChildren.set(owner, index => { while (offset <= index && offset < nodes.length) batch(); });
    };
    tree.append(jump(root)); children(tree, root);
  };
  side.onchange = render; render();
  return { getLocation: () => target ? { side: side.value, line: (side.value === "Before" ? oldLines : newLines).get(target) } : null,
    selectRow: (row: HTMLElement, preferredSide?: string) => {
    const desiredSide = preferredSide ?? (row.classList.contains("payload-remove") ? "Before"
      : row.classList.contains("payload-add") ? "After" : side.value);
    if (side.value !== desiredSide) { side.value = desiredSide; render(); }
    const line = (side.value === "After" ? newLines : oldLines).get(row);
    let node = side.value === "After" ? after : before;
    if (!node || line === undefined) return;
    while (true) {
      const index: number = node.children.findIndex(child => child.line <= line && child.endLine >= line);
      if (index === -1) break;
      revealChildren.get(node)?.(index);
      node = node.children[index];
    }
    const button = buttons.get(node);
    if (!button) return;
    // Ancestors may already be populated but manually collapsed.
    for (let parent = button.parentElement; parent && parent !== tree; parent = parent.parentElement) {
      if (parent instanceof HTMLDetailsElement) parent.open = true;
    }
    select(button, row);
    row.scrollIntoView({ block: "center", inline: "nearest" });
    // Only scroll the sidebar itself; scrollIntoView here would move the diff too.
    const bounds = button.getBoundingClientRect(), viewport = outline.getBoundingClientRect();
    if (bounds.top < viewport.top || bounds.bottom > viewport.bottom) {
      outline.scrollTop += bounds.top - viewport.top - outline.clientHeight / 2 + bounds.height / 2;
    }
  } };
}
