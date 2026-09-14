// Bounded Myers line diff. Large unrelated bodies fall back to a complete,
// explicitly labelled replacement, never silently omit payload lines.
import { payloadOutline } from "./payload-outline-model";
type Line = { kind: "same" | "add" | "remove"; text: string };
function diff(a: string[], b: string[]): { lines: Line[]; fallback: boolean } {
  let prefix = 0, suffix = 0;
  while (prefix < a.length && prefix < b.length && a[prefix] === b[prefix]) prefix++;
  while (suffix < a.length - prefix && suffix < b.length - prefix && a[a.length - suffix - 1] === b[b.length - suffix - 1]) suffix++;
  const old = a.slice(prefix, a.length - suffix), next = b.slice(prefix, b.length - suffix);
  const same = (items: string[]): Line[] => items.map(text => ({ kind: "same", text }));
  const trace: Map<number, number>[] = [];
  let v = new Map<number, number>([[1, 0]]);
  const start = performance.now();
  for (let d = 0; d <= Math.min(old.length + next.length, 400); d++) {
    if (performance.now() - start > 1500) break;
    trace.push(new Map(v));
    for (let k = -d; k <= d; k += 2) {
      let x = k === -d || (k !== d && (v.get(k - 1) ?? -1) < (v.get(k + 1) ?? -1))
        ? v.get(k + 1) ?? 0 : (v.get(k - 1) ?? 0) + 1;
      let y = x - k;
      while (x < old.length && y < next.length && old[x] === next[y]) { x++; y++; }
      v.set(k, x);
      if (x >= old.length && y >= next.length) {
        const middle: Line[] = [];
        for (let step = d; step >= 0; step--) {
          const prev = trace[step], diagonal = x - y;
          const pk = diagonal === -step || (diagonal !== step && (prev.get(diagonal - 1) ?? -1) < (prev.get(diagonal + 1) ?? -1)) ? diagonal + 1 : diagonal - 1;
          const px = prev.get(pk) ?? 0, py = px - pk;
          while (x > px && y > py) { middle.push({ kind: "same", text: old[--x] }); y--; }
          if (step > 0) {
            if (x === px) middle.push({ kind: "add", text: next[--y] });
            else middle.push({ kind: "remove", text: old[--x] });
          }
        }
        return { lines: [...same(a.slice(0, prefix)), ...middle.reverse(), ...same(a.slice(a.length - suffix))], fallback: false };
      }
    }
  }
  return { lines: [...same(a.slice(0, prefix)), ...old.map(text => ({ kind: "remove" as const, text })), ...next.map(text => ({ kind: "add" as const, text })), ...same(a.slice(a.length - suffix))], fallback: true };
}
self.onmessage = event => {
  const before = event.data.before === undefined ? [] : JSON.stringify(event.data.before, null, 2).split("\n");
  const after = JSON.stringify(event.data.after, null, 2).split("\n");
  self.postMessage({ ...diff(before, after), beforeOutline: payloadOutline(event.data.before), afterOutline: payloadOutline(event.data.after) });
};
