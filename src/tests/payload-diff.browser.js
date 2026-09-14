// Validate the built worker against complete before/after reconstruction.
async (page) => {
  const context = await page.context().browser().newContext();
  try {
    await context.route("**/api/sessions/active", route => route.fulfill({ json: null }));
    const view = await context.newPage();
    await view.goto("http://127.0.0.1:8765");
    return await view.evaluate(async () => {
      const source = await (await fetch(document.querySelector('script[type="module"]').src)).text();
      const path = source.match(/\/assets\/payload-diff\.worker-[\w-]+\.js/)[0];
      const worker = new Worker(path, { type: "module" });
      const run = (before, after) => new Promise((resolve, reject) => {
        worker.onmessage = event => resolve(event.data);
        worker.onerror = reject;
        worker.postMessage({ before, after });
      });
      let count = 0;
      const check = async (before, after) => {
        const result = await run(before, after);
        const old = result.lines.filter(line => line.kind !== "add").map(line => line.text);
        const next = result.lines.filter(line => line.kind !== "remove").map(line => line.text);
        const expected = v => v === undefined ? [] : JSON.stringify(v, null, 2).split("\n");
        if (JSON.stringify(old) !== JSON.stringify(expected(before)) || JSON.stringify(next) !== JSON.stringify(expected(after))) throw new Error(`Lossy diff case ${count}`);
        for (const [value, outline] of [[before, result.beforeOutline], [after, result.afterOutline]]) {
          if (value === undefined) { if (outline !== null) throw new Error("Absent baseline outline"); continue; }
          const lines = expected(value);
          let seen = 0;
          const visit = (node, current, pointer) => {
            if (node.path !== pointer) throw new Error("Incorrect JSON Pointer");
            if (node.endLine !== node.line + JSON.stringify(current, null, 2).split("\n").length - 1) throw new Error("Incorrect outline range");
            const text = lines[node.line - 1].trim();
            const serialized = JSON.stringify(current, null, 2).split("\n")[0];
            if (!text.includes(serialized)) throw new Error(`Outline line mismatch: ${pointer}`);
            const entries = current !== null && typeof current === "object" ? Object.entries(current) : [];
            if (entries.length !== node.children.length) throw new Error("Missing outline nodes");
            entries.forEach(([key, child], i) => visit(node.children[i], child, `${pointer}/${key.replace(/~/g, "~0").replace(/\//g, "~1")}`));
            seen++;
          };
          visit(outline, value, "");
          if (!seen) throw new Error("Missing root");
        }
        count++; return result;
      };
      try {
        for (const [value, label] of [
          [{ a: 1, b: 2, c: 3, d: 4, e: 5, f: 6, g: 7, h: 8 }, "8 fields"],
          [{ a: 1 }, "1 field"], [{}, "0 fields"],
          [[1], "1 item"], [[], "0 items"], [[1, 2], "2 items"],
          [null, "null"], ["fixture", "string"], [true, "boolean"], [42, "number"],
        ]) {
          const result = await check(value, value);
          for (const root of [result.beforeOutline, result.afterOutline]) {
            if (root.label !== `Request payload · ${label}` || root.path !== "" || root.line !== 1) throw new Error("Incorrect readable root label or target");
          }
        }
        await check(undefined, { first: true });
        const identical = await check({ text: "same" }, { text: "same" });
        if (identical.lines.some(line => line.kind !== "same")) throw new Error("Identical payload changed");
        await check({ values: [1, 2, 3] }, { values: [1, 4, 3] });
        await check({ text: '<img src=x onerror=alert(1)>\nline' }, {});
        await check({ 'a/b~c': { empty: [], nested: [null, {}, { text: 'escaped\nline', role: 'user' }] } },
          { system: [{ type: 'text', text: 'system fixture' }], messages: [{ role: 'user', content: 'user fixture' }], tools: [{ name: 'Bash', input_schema: {} }] });
        let seed = 42;
        const random = () => { seed = (1664525 * seed + 1013904223) >>> 0; return seed % 8; };
        for (let n = 0; n < 150; n++) {
          const before = Array.from({ length: random() * 5 }, () => random());
          const after = Array.from({ length: random() * 5 }, () => random());
          await check(before, after);
        }
        const large = await check(Array.from({ length: 600 }, (_, i) => `old-${i}`), Array.from({ length: 600 }, (_, i) => `new-${i}`));
        if (!large.fallback) throw new Error("Expected bounded fallback");
        return { reconstructionCases: count, firstRequest: true, identical: true, boundedFallback: true };
      } finally { worker.terminate(); }
    });
  } finally { await context.close(); }
}
