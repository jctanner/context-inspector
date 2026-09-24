"""Read-only, bounded REST access to the MLflow service owned by this stack."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from fastapi import HTTPException
from .mlflow import MLflowSettings

MAX_BYTES = 16 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9_.:-]{1,200}\Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decoded(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def summary(info: dict) -> dict:
    metadata = info.get("trace_metadata", {})
    if not isinstance(metadata, dict) or not isinstance(info.get("trace_id"), str):
        raise HTTPException(502, "MLflow returned invalid trace metadata.")
    return {"trace_id": info.get("trace_id"), "state": info.get("state", "UNKNOWN"),
            "request_time": info.get("request_time"), "duration": info.get("execution_duration"),
            "request_preview": decoded(info.get("request_preview", info.get("request", ""))),
            "response_preview": decoded(info.get("response_preview", info.get("response", ""))),
            "session_id": metadata.get("mlflow.trace.session"),
            "turn_id": metadata.get("codex.turn_id"),
            "inspector_session_id": metadata.get("context_inspector.session_id"),
            "usage": decoded(metadata.get("mlflow.trace.tokenUsage")),
            "evidence": metadata.get("context_inspector.evidence", "MLflow trace; attribution supplied by exporter"),
            "metadata": metadata}


class MLflowTraces:
    def __init__(self):
        self.settings = MLflowSettings.from_environment()
        self.experiment = os.environ.get("CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID", "")
        self.owned = bool(re.fullmatch(r"context-inspector-mlflow-[a-f0-9]{32}",
                                      os.environ.get("CONTEXT_INSPECTOR_MLFLOW_CONTAINER", "")))
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def status(self) -> dict:
        ready = self.settings.enabled and self.settings.tracing_enabled and self.owned and self.experiment.isdigit()
        if not self.settings.enabled:
            message = "MLflow is disabled for this stack."
        elif not self.settings.tracing_enabled:
            message = "MLflow trace export is disabled for this stack."
        elif not ready:
            message = "No stack-owned MLflow experiment is available. Start the stack with tracing enabled."
        else:
            message = "Traces from this stack run. MLflow data is cleared when the stack shuts down."
        return {"available": ready, "message": message, "experiment_name": self.settings.experiment_name}

    def _require(self):
        if not self.status()["available"]:
            raise HTTPException(503, self.status()["message"])

    def _request(self, path: str, body: dict | None = None) -> dict:
        request = Request(self.settings.url + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=10) as response:
                content = response.read(MAX_BYTES + 1)
                if len(content) > MAX_BYTES:
                    raise HTTPException(502, "MLflow response exceeds the 16 MiB viewer limit.")
                data = json.loads(content)
                if not isinstance(data, dict):
                    raise ValueError("Expected object")
                return data
        except HTTPError as error:
            error.close()
            raise HTTPException(404 if error.code == 404 else 502,
                                "Trace not found in MLflow." if error.code == 404 else "MLflow could not serve this request.") from None
        except (URLError, TimeoutError, OSError):
            raise HTTPException(503, "MLflow is unavailable. Check that the stack's MLflow service is running.") from None
        except (ValueError, UnicodeError):
            raise HTTPException(502, "MLflow returned invalid trace data.") from None

    def search(self, session_id: str = "", page_token: str = "") -> dict:
        self._require()
        if session_id and not ID.fullmatch(session_id):
            raise HTTPException(400, "Invalid native session ID.")
        if len(page_token) > 4096:
            raise HTTPException(400, "Invalid page token.")
        body = {"locations": [{"mlflow_experiment": {"experiment_id": self.experiment}}],
                "max_results": 50, "order_by": ["timestamp_ms DESC"]}
        if session_id:
            body["filter"] = f"request_metadata.`mlflow.trace.session` = '{session_id}'"
        if page_token:
            body["page_token"] = page_token
        value = self._request("/api/3.0/mlflow/traces/search", body)
        traces = value.get("traces", [])
        if not isinstance(traces, list) or any(not isinstance(t, dict) for t in traces):
            raise HTTPException(502, "MLflow returned invalid trace summaries.")
        return {"traces": [summary(t) for t in traces], "next_page_token": value.get("next_page_token", "")}

    def detail(self, trace_id: str) -> dict:
        self._require()
        if not ID.fullmatch(trace_id) or trace_id in {".", ".."}:
            raise HTTPException(400, "Invalid trace ID.")
        # Metadata endpoint also verifies membership before any span/artifact fetch.
        meta = self._request("/api/3.0/mlflow/traces/" + trace_id)
        trace = meta.get("trace")
        info = trace.get("trace_info") if isinstance(trace, dict) else None
        if not isinstance(info, dict) or info.get("trace_id") != trace_id:
            raise HTTPException(502, "MLflow returned invalid trace metadata.")
        experiment = info.get("trace_location", {}).get("mlflow_experiment", {}).get("experiment_id")
        if str(experiment) != self.experiment:
            raise HTTPException(404, "Trace is not in this stack's experiment.")
        # This is MLflow's own UI artifact endpoint. Unlike the recorded failing
        # /traces/get endpoint, it supports traces stored in artifact repositories.
        data = self._request("/ajax-api/3.0/mlflow/get-trace-artifact?" + urlencode({"request_id": trace_id}))
        spans = data.get("spans", [])
        if not isinstance(spans, list) or any(not isinstance(s, dict) for s in spans):
            raise HTTPException(502, "MLflow returned invalid span data.")
        normalized = []
        for span in spans:
            if not isinstance(span.get("attributes", {}), dict) or not isinstance(span.get("context", {}), dict):
                raise HTTPException(502, "MLflow returned invalid span attributes.")
            attributes = {k: decoded(v) for k, v in span.get("attributes", {}).items()}
            normalized.append({"id": span.get("context", {}).get("span_id", span.get("span_id")),
                               "parent_id": span.get("parent_id", span.get("parent_span_id")), "name": span.get("name", "Unnamed span"),
                               "type": attributes.get("mlflow.spanType", "UNKNOWN"),
                               "start_ns": str(span.get("start_time_unix_nano", span.get("start_time", span.get("start_time_ns", "")))),
                               "end_ns": str(span.get("end_time_unix_nano", span.get("end_time", span.get("end_time_ns", "")))),
                               "status": span.get("status"), "inputs": attributes.get("mlflow.spanInputs"),
                               "outputs": attributes.get("mlflow.spanOutputs"),
                               "usage": attributes.get("mlflow.chat.tokenUsage"), "attributes": attributes})
        return {"trace": summary(info), "spans": normalized,
                "raw": json.dumps({"trace_info": info, "data": data}, indent=2), "source": "MLflow trace metadata and span artifact"}
