import { addPayloadView } from "./payload-diff";
import { element } from "./readable";

type ResponseEvidence = { flow_id: string; detail_url?: string; exact_response: Record<string, unknown> };
export type ResponseChoice = { number: number; response: ResponseEvidence };

/** Parse every SSE record for browsing; retain raw fields and non-JSON data. */
export function responsePayload(response: ResponseEvidence): unknown {
  const body = response.exact_response.body as { decoded?: { kind?: string; value?: unknown } } | undefined;
  if (body?.decoded?.kind !== "sse" || typeof body.decoded.value !== "string") {
    throw new Error("Decoded response SSE unavailable; no reconstructed reply was substituted");
  }
  const records = body.decoded.value.replace(/\r\n|\r/g, "\n").split("\n\n");
  const events = records.flatMap((raw, index) => {
    if (!raw) return [];
    const fields = raw.split("\n");
    const data = fields.filter(line => line === "data" || line.startsWith("data:"))
      .map(line => line === "data" ? "" : line.slice(5).replace(/^ /, "")).join("\n");
    let value: unknown = data, format = "text";
    try { value = JSON.parse(data); format = "json"; } catch { /* Keep non-JSON data, including [DONE]. */ }
    return [{ event: fields.filter(line => line.startsWith("event:")).at(-1)?.slice(6).replace(/^ /, "") ?? "message",
      data: value, data_format: format, terminated: index < records.length - 1, raw_fields: fields }];
  });
  return { events };
}

export function addResponsePayload(parent: HTMLElement, structured: HTMLElement, response: ResponseEvidence,
  choices: ResponseChoice[], signal: AbortSignal): void {
  const label = element("label", "response-comparison", "Compare with ");
  const select = document.createElement("select"); select.className = "response-baseline";
  const none = document.createElement("option"); none.value = ""; none.textContent = "None — full response"; select.append(none);
  for (const choice of choices) {
    const option = document.createElement("option"); option.value = choice.response.flow_id;
    option.textContent = `Response #${choice.number} · ${choice.response.flow_id}`; select.append(option);
  }
  label.append(select);
  const note = element("p", "comparison-label", "Decoded response events · parsed from captured SSE, not a single wire JSON document. Comparison choices are earlier responses in loaded history, not confirmed same-thread baselines. Raw SSE and wire bytes remain under Readable reply & evidence.");
  const host = element("div", "response-payload-host", "");
  parent.replaceChildren(label, note, host);
  let controller: AbortController | undefined;
  signal.addEventListener("abort", () => controller?.abort(), { once: true });
  const render = () => {
    controller?.abort(); controller = new AbortController();
    const renderSignal = controller.signal;
    if (signal.aborted) { controller.abort(); return; }
    structured.hidden = false; host.replaceChildren(structured);
    const choice = choices.find(item => item.response.flow_id === select.value);
    addPayloadView(host, structured, renderSignal, {
      payloadLabel: "Decoded response events", structuredLabel: "Readable reply & evidence", tableLabel: "Decoded response events payload", rootLabel: "Response events",
      load: async () => {
        const after = responsePayload(response);
        let before: unknown;
        if (choice) {
          let baseline = choice.response;
          if (baseline.detail_url) {
            const result = await fetch(baseline.detail_url, { cache: "no-store", signal: renderSignal });
            if (!result.ok) throw new Error("Selected response baseline unavailable; no substitute used");
            baseline = await result.json();
          }
          before = responsePayload(baseline);
        }
        return { before, after, fullOnly: !choice,
          provenance: `Complete decoded response events, pretty-printed; raw_fields preserve SSE fields. Flow ${response.flow_id}. ${choice ? `User-selected baseline: Response #${choice.number} · flow ${choice.response.flow_id}. No thread relationship inferred.` : "No comparison selected; lines are neutral, not additions."}` };
      },
    });
  };
  select.onchange = render; render();
}
