"""Print a synthetic Codex replay fixture for codex-inspection.browser.js."""
import json
from src.tests.test_codex_context import Wire
from src.server.codex_context import CodexContext

wire = Wire()
wire.create(instructions="Synthetic instructions", tools=[{"type": "function", "name": "lookup"}])
wire.server()
wire.server("completed", output=[{"type": "message", "content": [{"type": "output_text", "text": "Synthetic Codex reply"}]}],
            usage={"input_tokens": 120, "input_tokens_details": {"cached_tokens": 80}, "output_tokens": 30,
                   "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 150})
wire.create(previous_response_id="resp-1", input=[{"type": "function_call_output", "call_id": "call-synthetic", "output": "Synthetic result"}])
adapter = CodexContext()
events = [derived for event in wire.events for derived in adapter.consume(event)]
print(json.dumps({"events": events, "cursor": len(events), "total": 2, "next_before": None,
                  "latest_usage": next(event for event in events if event["kind"] == "context.usage")}))
