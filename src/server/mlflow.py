"""Disposable MLflow infrastructure for the normal stack entrypoint only."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import json
import hashlib
import os
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4


log = logging.getLogger(__name__)
PLUGIN_PROJECT = Path(__file__).resolve().parents[1] / "runtime" / "mlflow"
PLUGIN_ROOT = PLUGIN_PROJECT / "node_modules" / "@mlflow" / "claude-code"
RUNTIME_KEYS = ("CONTEXT_INSPECTOR_MLFLOW_CONTAINER", "CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID",
                "CONTEXT_INSPECTOR_TRACING_AGENT_IMAGE")


@dataclass(frozen=True)
class MLflowSettings:
    enabled: bool = True
    image: str = "ghcr.io/mlflow/mlflow:v3.16.0"
    host: str = "127.0.0.1"
    port: int = 5000
    allowed_hosts: str = "localhost:*,127.0.0.1:*"
    cors_allowed_origins: str = "http://localhost:*,http://127.0.0.1:*"
    network: str = "agent-mitm-network"
    tracing_enabled: bool = True
    experiment_name: str = "Claude Code"

    @classmethod
    def from_environment(cls) -> "MLflowSettings":
        enabled = os.environ.get("CONTEXT_INSPECTOR_MLFLOW_ENABLED", "1")
        if enabled not in {"0", "1"}:
            raise ValueError("CONTEXT_INSPECTOR_MLFLOW_ENABLED must be 0 or 1")
        tracing = os.environ.get("CONTEXT_INSPECTOR_MLFLOW_TRACING_ENABLED", "1")
        if tracing not in {"0", "1"}:
            raise ValueError("CONTEXT_INSPECTOR_MLFLOW_TRACING_ENABLED must be 0 or 1")
        settings = cls(
            enabled=enabled == "1",
            image=os.environ.get("CONTEXT_INSPECTOR_MLFLOW_IMAGE", cls.image),
            host=os.environ.get("CONTEXT_INSPECTOR_MLFLOW_HOST", cls.host),
            port=int(os.environ.get("CONTEXT_INSPECTOR_MLFLOW_PORT", str(cls.port))),
            allowed_hosts=os.environ.get("CONTEXT_INSPECTOR_MLFLOW_ALLOWED_HOSTS", cls.allowed_hosts),
            cors_allowed_origins=os.environ.get("CONTEXT_INSPECTOR_MLFLOW_CORS_ALLOWED_ORIGINS", cls.cors_allowed_origins),
            network=os.environ.get("MITM_NETWORK_NAME", cls.network),
            tracing_enabled=tracing == "1",
            experiment_name=os.environ.get("CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_NAME", cls.experiment_name),
        )
        if settings.host not in {"127.0.0.1", "0.0.0.0"}:
            raise ValueError("MLflow bind host must be 127.0.0.1 or 0.0.0.0")
        if not 1 <= settings.port <= 65535:
            raise ValueError("MLflow port must be between 1 and 65535")
        if not settings.image or settings.image.startswith("-") or not settings.allowed_hosts.strip():
            raise ValueError("MLflow image and allowed hosts must be non-empty")
        if not settings.network or settings.network.startswith("-") or not settings.experiment_name.strip():
            raise ValueError("MLflow network and experiment name must be non-empty")
        if not settings.cors_allowed_origins.strip():
            raise ValueError("MLflow browser origins must be non-empty")
        return settings

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def container_command(settings: MLflowSettings, name: str) -> list[str]:
    return [
        "podman", "run", "--detach", "--rm", "--name", name,
        "--label", "context-inspector.service=mlflow",
        "--network", settings.network,
        "--publish", f"{settings.host}:{settings.port}:5000",
        "--workdir", "/tmp", "--entrypoint", "mlflow", settings.image,
        "server", "--host", "0.0.0.0", "--port", "5000",
        "--workers", "1",
        "--backend-store-uri", "sqlite:////tmp/mlflow.db",
        "--serve-artifacts", "--artifacts-destination", "/tmp/mlflow-artifacts",
        "--allowed-hosts", f"{settings.allowed_hosts},{name}:5000",
        "--cors-allowed-origins", settings.cors_allowed_origins,
    ]


def prepare_agent_image() -> str:
    base_image = os.environ.get("AGENT_IMAGE", "localhost/claude-task-runner:latest")
    base_id = subprocess.run(["podman", "image", "inspect", "--format", "{{.Id}}", base_image],
                             check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    context = PLUGIN_PROJECT / "image"
    digest = hashlib.sha256(base_id.encode() + (context / "Containerfile").read_bytes()).hexdigest()[:20]
    image = f"localhost/context-inspector-claude-tracing:{digest}"
    if subprocess.run(["podman", "image", "exists", image], check=False).returncode:
        print("Building Claude tracing image (adds Node; leaves the base image unchanged)…", flush=True)
        subprocess.run(["podman", "build", "--build-arg", f"BASE_IMAGE={base_image}",
                        "--tag", image, str(context)], check=True, timeout=600)
    return image


def prepare_runtime(settings: MLflowSettings) -> str:
    agent_image = ""
    if settings.tracing_enabled:
        expected = json.loads((PLUGIN_PROJECT / "package.json").read_text())["dependencies"]["@mlflow/claude-code"]
        try:
            installed = json.loads((PLUGIN_ROOT / "package.json").read_text())["version"]
        except (OSError, ValueError, KeyError):
            installed = None
        if installed != expected or not (PLUGIN_ROOT / "bundle" / "stop.cjs").is_file():
            print("Installing pinned Claude MLflow tracing plugin…", flush=True)
            subprocess.run(["npm", "--prefix", str(PLUGIN_PROJECT), "ci", "--ignore-scripts",
                            "--no-audit", "--no-fund"], check=True, timeout=300)
        agent_image = prepare_agent_image()
    exists = subprocess.run(["podman", "network", "exists", settings.network], check=False)
    if exists.returncode:
        subprocess.run(["podman", "network", "create", "--ignore", settings.network], check=True, timeout=30)
    return agent_image


def create_experiment(settings: MLflowSettings) -> str:
    # The server was just created, so no previous experiment ID is valid.
    request = Request(settings.url + "/api/2.0/mlflow/experiments/create",
                      data=json.dumps({"name": settings.experiment_name}).encode(),
                      headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
        experiment_id = str(json.load(response)["experiment_id"])
    if not experiment_id.isdigit():
        raise RuntimeError("MLflow returned an invalid experiment ID")
    return experiment_id


@contextmanager
def tracing_environment(name: str = "", experiment_id: str = "", agent_image: str = ""):
    previous = {key: os.environ.get(key) for key in RUNTIME_KEYS}
    os.environ.update(dict(zip(RUNTIME_KEYS, (name, experiment_id, agent_image))))
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def wait_ready(name: str, settings: MLflowSettings, timeout: float = 120) -> None:
    # A host HTTP_PROXY must not redirect our local readiness probe.
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = subprocess.run(
            ["podman", "inspect", "--format", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=10,
        )
        if state.returncode or state.stdout.strip() != "true":
            raise RuntimeError(f"MLflow container {name} exited before becoming ready")
        try:
            with opener.open(settings.url + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"MLflow did not become healthy within {timeout:g}s ({name})")


@contextmanager
def mlflow_service(settings: MLflowSettings):
    if not settings.enabled:
        with tracing_environment():
            yield
        return
    agent_image = prepare_runtime(settings)
    name = f"context-inspector-mlflow-{uuid4().hex}"
    print(f"Starting MLflow ({name}); first launch may pull {settings.image}", flush=True)
    try:
        # Inherit output so pulls/startup failures remain visible, without buffering logs.
        subprocess.run(container_command(settings, name), check=True, timeout=600)
        wait_ready(name, settings)
        print(f"MLflow ready: {settings.url} (ephemeral; erased on stack shutdown)", flush=True)
        experiment_id = create_experiment(settings) if settings.tracing_enabled else ""
        with tracing_environment(name if settings.tracing_enabled else "", experiment_id, agent_image):
            if settings.tracing_enabled:
                print(f"Claude tracing enabled: {settings.experiment_name} (experiment {experiment_id})", flush=True)
            yield
    finally:
        try:
            result = subprocess.run(
                ["podman", "rm", "--force", "--time", "10", "--ignore", name],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode:
                log.warning("MLflow cleanup failed; remove container %s manually: %s", name, result.stderr.strip())
        except (OSError, subprocess.SubprocessError):
            log.exception("MLflow cleanup failed; remove container %s manually", name)
