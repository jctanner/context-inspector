from pathlib import Path
import unittest


class ReadmeArchitectureTests(unittest.TestCase):
    def test_introduction_leads_with_live_block_by_block_diffs(self) -> None:
        readme = (Path(__file__).parents[2] / "README.md").read_text()
        architecture = readme.index("## Architecture")
        introduction = readme[:architecture]
        self.assertIn("context block by block", introduction)
        for change in ("**added**", "**removed**", "**transformed**", "**retained**"):
            self.assertIn(change, introduction)
        self.assertIn("correlated model response and measured context usage", introduction)
        self.assertIn("model call rather than a user turn", introduction)
        self.assertIn("not reconstructed from the terminal transcript", introduction)

    def test_architecture_diagram_covers_control_traffic_and_evidence_paths(self) -> None:
        readme = (Path(__file__).parents[2] / "README.md").read_text()
        self.assertIn("```mermaid\nflowchart LR", readme)
        for label in (
            "Browser on the host",
            "xterm.js Claude terminal",
            "Loopback Context Inspector application",
            "Runtime orchestration script<br/>src/runtime/run.sh",
            "Podman engine",
            "Private Podman network",
            "Agent container<br/>real Claude CLI",
            "mitmproxy sidecar<br/>live-capture addon",
            "Google Vertex AI<br/>Claude endpoint",
            "keystrokes, resize, and raw terminal bytes<br/>terminal WebSocket",
            "PTY input and output",
            "stdin and stdout of run.sh",
            "foreground podman attach",
            "container TTY",
            "requests foreground agent lifecycle",
            "requests detached proxy lifecycle",
            "exit trap requests proxy removal",
            "model HTTPS through configured proxy",
            "Versioned live events<br/>events.jsonl",
            "Persistent Claude state<br/>.state/claude",
            "generated CA trust mount",
            "read-only ADC mount",
        ):
            self.assertIn(label, readme)
        self.assertIn("server relays unmodified\nPTY bytes", readme)
        self.assertIn("The browser does\nnot call a model SDK", readme)
        self.assertIn("without replacing the raw capture", readme)


if __name__ == "__main__":
    unittest.main()
