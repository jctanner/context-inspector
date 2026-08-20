from pathlib import Path
import unittest


class WebLayoutRegressionTests(unittest.TestCase):
    def test_desktop_shell_constrains_content_to_internal_scrollers(self) -> None:
        css = (Path(__file__).parents[1] / "web" / "style.css").read_text()
        self.assertIn("grid-template-rows: 5.5rem minmax(0, 1fr)", css)
        self.assertIn(".workspace { --terminal-width: 50%; min-height: 0; overflow: hidden;", css)
        self.assertIn(".pane { min-width: 0; min-height: 0; overflow: hidden;", css)
        self.assertIn(".flow-events { min-height: 0; flex: 1; overflow: auto;", css)

    def test_response_blocks_are_collapsed_by_flow(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "main.ts").read_text()
        self.assertIn("const responseRows = new Map<string, ResponseRow>()", source)
        self.assertIn('event.kind === "response.block"', source)
        self.assertIn("transport chunks collapsed", source)

    def test_browser_persists_and_resumes_session(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "main.ts").read_text()
        self.assertIn('const SESSION_STORAGE_KEY = "context-inspector.active-session"', source)
        self.assertIn("localStorage.setItem(SESSION_STORAGE_KEY, id)", source)
        self.assertIn("async function resumePersistedSession", source)

    def test_context_meter_retains_last_measurement_during_next_request(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "main.ts").read_text()
        render_start = source.index("function renderContextDiff")
        render_end = source.index("function renderContextUsage")
        request_transition = source[render_start:render_end]
        self.assertIn("if (hasContextMeasurement)", request_transition)
        self.assertIn("Showing the previous completed measurement", request_transition)
        self.assertNotIn('contextMeterProgress.removeAttribute("value")', request_transition)

    def test_unmeasured_context_meter_is_static(self) -> None:
        web = Path(__file__).parents[1] / "web"
        html = (web / "index.html").read_text()
        source = (web / "main.ts").read_text()
        self.assertIn('id="context-meter-progress" max="100" value="0"', html)
        self.assertIn("contextMeterProgress.value = 0", source)
        self.assertNotIn('contextMeterProgress.removeAttribute("value")', source)

    def test_context_diff_labels_request_provenance(self) -> None:
        web = Path(__file__).parents[1] / "web"
        html = (web / "index.html").read_text()
        source = (web / "main.ts").read_text()
        self.assertIn("Model request context changes", html)
        self.assertIn("Request only · normalized from the captured API request", source)
        self.assertIn("request-context blocks", source)
        self.assertIn("Response content is not included", source)

    def test_correlated_responses_are_visibly_separate(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "main.ts").read_text()
        self.assertIn('kind: "context.response"', source)
        self.assertIn("const requestRows = new Map<string, HTMLLIElement>()", source)
        self.assertIn("Correlated model response", source)
        self.assertIn("correlated by exact flow_id", source)
        self.assertIn("Reconstructed response content blocks", source)
        self.assertIn("Exact captured response metadata and wire bytes", source)
        self.assertIn("Losslessly decoded response SSE", source)
        self.assertIn("Purpose:", source)

    def test_internal_calls_cannot_remain_the_headline_context_measurement(self) -> None:
        web = Path(__file__).parents[1] / "web"
        html = (web / "index.html").read_text()
        source = (web / "main.ts").read_text()
        self.assertIn("Latest non-internal request context size", html)
        self.assertIn("const usageByFlow = new Map<string, ContextUsage>()", source)
        self.assertIn("const internalFlows = new Set<string>()", source)
        self.assertIn('response.purpose.classification.startsWith("likely_internal_")', source)
        self.assertIn(".filter((usage) => !internalFlows.has(usage.flow_id))", source)
        self.assertIn("internalFlows.has(displayed.flow_id) || usage.sequence >= displayed.sequence", source)
        self.assertIn("Latest measured request not classified as internal", source)

    def test_internal_call_cards_receive_muted_semantic_styling(self) -> None:
        web = Path(__file__).parents[1] / "web"
        source = (web / "main.ts").read_text()
        css = (web / "style.css").read_text()
        self.assertIn('item.classList.add("purpose-internal")', source)
        self.assertIn("item.dataset.purpose = response.purpose.classification", source)
        self.assertIn(".flow-event.purpose-internal", css)
        self.assertIn("background: #eceff2", css)

    def test_request_purpose_and_harness_origin_are_visible(self) -> None:
        web = Path(__file__).parents[1] / "web"
        source = (web / "main.ts").read_text()
        css = (web / "style.css").read_text()
        self.assertIn("diff.request_purpose.classification.startsWith", source)
        self.assertIn("Request purpose:", source)
        self.assertIn("diff.comparison_lineage", source)
        self.assertIn("origin.startsWith(\"harness_injected_\")", source)
        self.assertIn("classified as harness-injected", source)
        self.assertIn(".harness-origin-summary", css)

    def test_clear_history_uses_a_persistent_session_event_watermark(self) -> None:
        web = Path(__file__).parents[1] / "web"
        html = (web / "index.html").read_text()
        source = (web / "main.ts").read_text()
        self.assertIn('id="clear-history"', html)
        self.assertIn('const CONTEXT_CURSOR_PREFIX = "context-inspector.context-after."', source)
        self.assertIn("function clearContextHistory", source)
        self.assertIn("String(latestContextSequence)", source)
        self.assertIn("contexts?after_sequence=${afterSequence}", source)
        self.assertIn("flowEventsElement.replaceChildren()", source)
        self.assertIn('clearHistoryButton.addEventListener("click", clearContextHistory)', source)


if __name__ == "__main__":
    unittest.main()
