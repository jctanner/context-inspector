/** Usage samples retain capture time; missing measurements never become zero. */
type Sample = { flow_id: string; sequence: number; occurred_at?: string | null; percent: number | null; used_input_tokens: number | null; context_window_tokens: number | null };
const ns = "http://www.w3.org/2000/svg";
function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string>, text?: string): SVGElementTagNameMap[K] {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text) node.textContent = text;
  return node;
}
export function renderContextHistory(samples: Sample[]): void {
  const host = document.querySelector<HTMLElement>("#context-history-chart")!;
  const note = document.querySelector<HTMLElement>("#context-history-note")!;
  const rows = samples.map(s => ({ ...s, time: Date.parse(s.occurred_at ?? "") }))
    .sort((a, b) => a.sequence - b.sequence);
  const valid = (s: typeof rows[number]) => Number.isFinite(s.time) && s.percent !== null && Number.isFinite(s.percent) && s.used_input_tokens !== null && s.context_window_tokens !== null;
  const points = rows.filter(valid);
  host.replaceChildren();
  note.textContent = points.length ? `${points.length} measured requests · loaded history · hover or focus a point for details` : "Awaiting measured percentages with capture timestamps.";
  if (!points.length) return;
  const min = Math.min(...points.map(s => s.time)), max = Math.max(...points.map(s => s.time));
  const ceiling = Math.max(100, ...points.map(s => s.percent!));
  const x = (time: number) => max === min ? 300 : 40 + (time - min) / (max - min) * 520;
  const y = (percent: number) => 104 - percent / ceiling * 88;
  const chart = svg("svg", {viewBox: "0 0 600 132", role: "group", "aria-label": "Context percentage by captured response time"});
  for (const tick of [0, ceiling / 2, ceiling]) {
    chart.append(svg("line", {x1: "40", x2: "560", y1: String(y(tick)), y2: String(y(tick)), class: "context-chart-grid"}),
      svg("text", {x: "34", y: String(y(tick) + 4), "text-anchor": "end"}, `${Math.round(tick)}%`));
  }
  let segment: string[] = [];
  const flush = () => {
    if (segment.length) chart.append(svg("polyline", {points: segment.join(" "), class: "context-chart-line"}));
    segment = [];
  };
  for (const row of rows) {
    if (!valid(row)) { flush(); continue; }
    segment.push(`${x(row.time)},${y(row.percent!)}`);
  }
  flush();
  for (const row of points) {
    const label = `${new Date(row.time).toLocaleString()} · ${row.percent!.toFixed(1)}% · ${row.used_input_tokens!.toLocaleString()} / ${row.context_window_tokens!.toLocaleString()} tokens · ${row.flow_id}`;
    const dot = svg("circle", {cx: String(x(row.time)), cy: String(y(row.percent!)), r: "3.5", tabindex: "0", role: "img", "aria-label": label, class: "context-chart-point"});
    dot.append(svg("title", {}, label));
    dot.onfocus = dot.onmouseenter = () => { note.textContent = label; };
    chart.append(dot);
  }
  const time = (value: number) => new Date(value).toLocaleTimeString();
  chart.append(svg("text", {x: "40", y: "126"}, time(min)), svg("text", {x: "560", y: "126", "text-anchor": "end"}, time(max)));
  host.append(chart);
}
