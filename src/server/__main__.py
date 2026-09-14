from __future__ import annotations

import uvicorn
import signal

from .app import create_app
from .config import Settings
from .mlflow import MLflowSettings, mlflow_service
from .startup_reset import clean_claude_startup


def main() -> None:
    settings = Settings.from_environment()
    settings.validate()
    mlflow = MLflowSettings.from_environment()
    if mlflow.enabled and mlflow.port == settings.port:
        raise ValueError("MLflow and Context Inspector must use different ports")

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    # Uvicorn handles signals while serving; cover image pull/readiness as well.
    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        with clean_claude_startup(enabled=settings.command_override is None):
            with mlflow_service(mlflow):
                uvicorn.run(create_app(settings=settings), host=settings.host, port=settings.port)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    main()
