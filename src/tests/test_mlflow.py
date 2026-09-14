from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
import os
import socket
import subprocess
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.server.mlflow import MLflowSettings, container_command, mlflow_service, wait_ready


class MLflowTests(unittest.TestCase):
    def setUp(self):
        prepare = patch("src.server.mlflow.prepare_runtime", return_value="localhost/test-tracing:fixture")
        prepare.start()
        self.addCleanup(prepare.stop)
        experiment = patch("src.server.mlflow.create_experiment", return_value="1")
        experiment.start()
        self.addCleanup(experiment.stop)

    @patch("src.server.__main__.create_app")
    @patch("src.server.__main__.uvicorn.run")
    @patch("src.server.__main__.MLflowSettings.from_environment")
    @patch("src.server.__main__.Settings.from_environment")
    def test_entrypoint_owns_service_around_uvicorn(self, settings, mlflow, serve, app):
        from src.server.__main__ import main
        settings.return_value.port = 8765
        settings.return_value.command_override = None
        mlflow.return_value = MLflowSettings()
        events = []

        @contextmanager
        def reset(*, enabled):
            self.assertTrue(enabled)
            events.append("reset")
            try:
                yield
            finally:
                events.append("unlock")

        @contextmanager
        def service(config):
            events.append("ready")
            try:
                yield
            finally:
                events.append("cleanup")

        serve.side_effect = lambda *args, **kwargs: events.append("serve")
        with patch("src.server.__main__.mlflow_service", service), patch("src.server.__main__.clean_claude_startup", reset):
            main()
        self.assertEqual(events, ["reset", "ready", "serve", "cleanup", "unlock"])
        settings.return_value.validate.assert_called_once()
        settings.return_value.port = 5000
        with self.assertRaisesRegex(ValueError, "different ports"):
            main()

    def test_defaults_and_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(MLflowSettings.from_environment(), MLflowSettings())
        with patch.dict(os.environ, {
            "CONTEXT_INSPECTOR_MLFLOW_ENABLED": "0",
            "CONTEXT_INSPECTOR_MLFLOW_PORT": "5001",
        }, clear=True):
            settings = MLflowSettings.from_environment()
            self.assertFalse(settings.enabled)
            self.assertEqual(settings.port, 5001)
        for key, value in [("ENABLED", "yes"), ("PORT", "0"), ("PORT", "65536"),
                           ("HOST", "public.example"), ("IMAGE", "-bad"), ("ALLOWED_HOSTS", "")]:
            with self.subTest(key=key, value=value), patch.dict(os.environ, {
                "CONTEXT_INSPECTOR_MLFLOW_" + key: value,
            }, clear=True), self.assertRaises(ValueError):
                MLflowSettings.from_environment()

    def test_no_shared_state_or_credentials(self):
        argv = container_command(MLflowSettings(), "test-name")
        self.assertIn("127.0.0.1:5000:5000", argv)
        self.assertIn("sqlite:////tmp/mlflow.db", argv)
        self.assertIn("/tmp/mlflow-artifacts", argv)
        self.assertIn("--rm", argv)
        for option in ["--volume", "-v", "--mount", "--env", "-e", "--env-file", "--network=host"]:
            self.assertNotIn(option, argv)

    def test_browser_origins_configuration(self):
        origins = "http://localhost:*,http://192.168.1.145:5000"
        with patch.dict(os.environ, {"CONTEXT_INSPECTOR_MLFLOW_CORS_ALLOWED_ORIGINS": origins}, clear=True):
            settings = MLflowSettings.from_environment()
            command = container_command(settings, "owned")
            self.assertEqual(command[command.index("--cors-allowed-origins") + 1], origins)
            self.assertNotIn("--disable-security-middleware", command)
            self.assertIn("owned:5000", command[command.index("--allowed-hosts") + 1])
        with patch.dict(os.environ, {"CONTEXT_INSPECTOR_MLFLOW_CORS_ALLOWED_ORIGINS": " "}, clear=True):
            with self.assertRaisesRegex(ValueError, "origins"):
                MLflowSettings.from_environment()

    @patch("src.server.mlflow.subprocess.run")
    def test_disabled_does_not_use_podman(self, run):
        with mlflow_service(MLflowSettings(enabled=False)):
            pass
        run.assert_not_called()

    @patch("src.server.mlflow.wait_ready")
    @patch("src.server.mlflow.subprocess.run")
    def test_lifecycle_unique_names_and_failure_cleanup(self, run, ready):
        run.return_value.returncode = 0
        names = []
        with redirect_stdout(StringIO()):
            for failure in [None, RuntimeError("application failure"), KeyboardInterrupt()]:
                try:
                    with mlflow_service(MLflowSettings()):
                        ready.assert_called()
                        names.append(ready.call_args.args[0])
                        if failure:
                            raise failure
                except (RuntimeError, KeyboardInterrupt):
                    pass
                self.assertEqual(run.call_args.args[0],
                                 ["podman", "rm", "--force", "--time", "10", "--ignore", names[-1]])
        self.assertEqual(len(set(names)), 3)

    @patch("src.server.mlflow.wait_ready", side_effect=RuntimeError("unhealthy"))
    @patch("src.server.mlflow.subprocess.run")
    def test_readiness_failure_prevents_app_start_and_cleans_up(self, run, ready):
        run.return_value.returncode = 0
        with redirect_stdout(StringIO()), self.assertRaisesRegex(RuntimeError, "unhealthy"):
            with mlflow_service(MLflowSettings()):
                self.fail("unhealthy service yielded")
        self.assertEqual(run.call_args.args[0][:2], ["podman", "rm"])

    @patch("src.server.mlflow.subprocess.run")
    def test_run_failure_cleans_up_and_propagates(self, run):
        run.side_effect = [subprocess.CalledProcessError(125, "podman"), Mock(returncode=0)]
        with redirect_stdout(StringIO()), self.assertRaises(subprocess.CalledProcessError):
            with mlflow_service(MLflowSettings()):
                self.fail("failed run yielded")
        self.assertEqual(run.call_args.args[0][:2], ["podman", "rm"])

    @patch("src.server.mlflow.time.sleep")
    @patch("src.server.mlflow.build_opener")
    @patch("src.server.mlflow.subprocess.run")
    def test_readiness_retries_then_succeeds(self, run, opener, sleep):
        run.return_value = Mock(returncode=0, stdout="true\n")
        response = Mock()
        response.__enter__ = Mock(return_value=Mock(status=200))
        response.__exit__ = Mock()
        opener.return_value.open.side_effect = [URLError("starting"), response]
        wait_ready("owned", MLflowSettings())
        sleep.assert_called_once()

    @patch("src.server.mlflow.subprocess.run")
    def test_early_exit_and_timeout(self, run):
        run.return_value = Mock(returncode=1, stdout="")
        with self.assertRaisesRegex(RuntimeError, "exited"):
            wait_ready("owned", MLflowSettings())
        with self.assertRaisesRegex(RuntimeError, "healthy"):
            wait_ready("owned", MLflowSettings(), timeout=0)


@unittest.skipUnless(os.environ.get("CONTEXT_INSPECTOR_TEST_MLFLOW") == "1", "opt-in Podman integration")
class MLflowContainerTests(unittest.TestCase):
    def test_browser_post_origin_allowlist(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        browser_host = "192.168.1.145:5000"
        browser_origin = f"http://{browser_host}"
        settings = MLflowSettings(
            port=port, tracing_enabled=False,
            allowed_hosts=f"localhost:*,127.0.0.1:*,{browser_host}",
            cors_allowed_origins=f"http://localhost:*,http://127.0.0.1:*,{browser_origin}",
        )
        with mlflow_service(settings):
            for origin, expected in [(browser_origin, 200), ("http://localhost:5000", 200),
                                     ("http://untrusted.example:5000", 403),
                                     ("http://192.168.1.145:5001", 403), (None, 200)]:
                with self.subTest(origin=origin):
                    headers = {"Host": browser_host, "Content-Type": "application/json"}
                    if origin:
                        headers["Origin"] = origin
                    request = Request(settings.url + "/api/2.0/mlflow/experiments/search",
                                      data=b'{"max_results":1}', headers=headers)
                    try:
                        response = urlopen(request, timeout=10)
                    except HTTPError as error:
                        response = error
                    with response:
                        self.assertEqual(response.status, expected, response.read().decode())
            request = Request(settings.url + "/api/2.0/mlflow/experiments/search",
                              data=b'{"max_results":1}', headers={"Host": "untrusted.example:5000",
                              "Origin": browser_origin, "Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as blocked:
                urlopen(request, timeout=10)
            with blocked.exception as error:
                self.assertIn(error.code, (400, 403))

    def test_ui_and_database_reset_across_launches(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        settings = MLflowSettings(port=port)
        artifact_url = settings.url + "/api/2.0/mlflow-artifacts/artifacts/smoke.txt"

        def api(path, payload):
            request = Request(settings.url + "/api/2.0/mlflow/" + path,
                              data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=10) as response:
                    return json.load(response)
            except HTTPError as error:
                with error:
                    self.fail(f"{path}: {error.code}: {error.read().decode()}")

        with mlflow_service(settings):
            with urlopen(settings.url, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"<html", response.read().lower())
            result = api("experiments/create", {"name": "ephemeral-smoke"})
            api("runs/create", {"experiment_id": result["experiment_id"], "start_time": 0})
            self.assertTrue(api("experiments/search", {"max_results": 100, "filter": "name = 'ephemeral-smoke'"}).get("experiments"))
            with urlopen(Request(artifact_url, data=b"disposable smoke fixture", method="PUT"), timeout=10) as response:
                self.assertEqual(response.status, 200)
            with urlopen(artifact_url, timeout=10) as response:
                self.assertEqual(response.read(), b"disposable smoke fixture")
        with mlflow_service(settings):
            self.assertFalse(api("experiments/search", {"max_results": 100, "filter": "name = 'ephemeral-smoke'"}).get("experiments"))
            with self.assertRaises(HTTPError) as missing:
                urlopen(artifact_url, timeout=10)
            with missing.exception as error:
                self.assertEqual(error.code, 404)


if __name__ == "__main__":
    unittest.main()
