# MLflow Codex gateway trace grouping

Investigated 2026-09-23. Local checkout HEAD: 25b1af314. Read-only source review,
not a live MLflow/Codex integration test or proof that our deployed MLflow image
has all checkout features.

## Findings

The guide routes Codex to /gateway/proxy/codex/v1. In the checkout,
mlflow/server/gateway_api.py:1622 defines raw_proxy as a POST catch-all. It wraps
each request's _do_proxy generator with maybe_traced_gateway_call at line 1704.
There is no WebSocket route in this gateway module.

mlflow/gateway/tracing_utils.py:192 implements maybe_traced_gateway_call. With
usage tracking enabled, it decorates the function using mlflow.trace and sends
it to the endpoint's experiment. Metadata includes endpoint ID, request type,
caller (explicit header or User-Agent product) and authenticated user metadata.
_get_user_metadata in gateway_api.py:199 only extracts auth username/user ID.
This path does not extract Codex conversation/thread/session IDs, use
previous_response_id to merge calls, or build a long-lived conversation root.

mlflow/gateway/providers/base.py:284 wraps the provider proxy operation in an
LLM span. This gives a gateway request trace with provider activity underneath,
not proven full agent/tool execution spans. Typed Responses streaming has an
output reducer in gateway/tracing_utils.py:606 that selects response.completed;
do not assume every raw-proxy route has identical structured output/usage parsing.

## Actual grouping mechanisms

1. Endpoint experiment groups traces for the configured endpoint.
2. traceparent can link a gateway call into an existing caller trace. In
   tracing_utils.py:138, _maybe_create_distributed_span creates lightweight
   gateway/model mirror spans in that caller's trace and links the separate full
   gateway trace via LINKED_GATEWAY_TRACE_ID. Request payloads stay in the gateway
   trace. Tests/gateway/test_tracing_utils.py:424 explicitly tests two separate
   traces and parent/child IDs; this requires caller-provided trace context.
3. MLflow supports session grouping through metadata mlflow.trace.session
   (tracing/constant.py:26). tracing/context.py:43 exposes session_id in
   tracing_context; tracing/fluent.py:1514 accepts session_id in
   update_current_trace. That capability is not automatically applied to Codex
   sessions by the reviewed raw-proxy path.
4. Separate OTLP ingestion recognizes codex_cli_rs and codex_vscode service
   names (server/otel_api.py:52). It preserves incoming span trace/parent IDs.
   It does not prove the gateway infers those relationships from model traffic,
   or that our CLI emits the desired agent/tool spans without configuration.

## Documentation caveats

https://mlflow.org/docs/latest/genai/governance/ai-gateway/coding-agents/codex/

The introduction says subscription authentication, but setup explicitly says an
API key is required instead of ChatGPT subscription. It also says every session
is a trace; the reviewed raw-proxy implementation creates a trace per invocation,
not an automatically reconstructed entire Codex conversation. We should not
repeat those broader claims without validating them. The OpenAI provider defaults
to api.openai.com/v1, whereas our observed OAuth runtime uses ChatGPT Responses
WebSockets. Copying the gateway setup is not a verified drop-in OAuth solution.

## Implications for Context Inspector

A request-level exporter from our existing capture is feasible without a
Claude-specific Stop hook. A reasonable first integration would create one trace
per observed model call and set session_id to Context Inspector's owned session
ID. This groups calls in MLflow without claiming that an inspector session is a
native Codex conversation or assigning unobserved primary/subagent roles.

Preserve captured request/response IDs, transport, correlation confidence, usage
and timestamps as provenance. WebSocket logical call boundaries already exist in
our adapter; do not use the connection ID as a model-call trace ID. Exact tool
execution hierarchy or native conversation grouping requires additional stable
identifiers or native telemetry. This is a proposed integration direction, not
implemented behavior. Main stack and active sessions unchanged.

## Follow-up: existing turn-level integration found

Task 091 found @mlflow/codex in libs/typescript/integrations/codex, a separate
notify/transcript integration that exports turn-level traces and native session
grouping. Prefer evaluating that existing package over building the request-only
exporter proposed above. See codex-mlflow-hooks.md. Gateway findings still apply
to the gateway route only.
