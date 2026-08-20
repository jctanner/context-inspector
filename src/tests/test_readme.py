from pathlib import Path
import unittest


class ReadmeArchitectureTests(unittest.TestCase):
    def test_architecture_diagram_covers_control_traffic_and_evidence_paths(self) -> None:
        readme = (Path(__file__).parents[2] / "README.md").read_text()
        self.assertIn("```mermaid\nflowchart LR", readme)
        for label in (
            "Browser on the host",
            "Loopback Context Inspector application",
            "Private Podman network",
            "Agent container<br/>real Claude CLI",
            "mitmproxy sidecar<br/>live-capture addon",
            "Google Vertex AI<br/>Claude endpoint",
            "terminal WebSocket",
            "model HTTPS through configured proxy",
            "Versioned live events<br/>events.jsonl",
            "Persistent Claude state<br/>.state/claude",
            "generated CA trust mount",
            "read-only ADC mount",
        ):
            self.assertIn(label, readme)
        self.assertIn("the browser does not call a\nmodel SDK", readme)
        self.assertIn("without replacing the raw capture", readme)


if __name__ == "__main__":
    unittest.main()
