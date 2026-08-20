from __future__ import annotations

import unittest

from src.server.identity import classify_request_stream


class StreamIdentityTests(unittest.TestCase):
    def test_agent_header_is_high_confidence_stream_identity(self) -> None:
        identity = classify_request_stream({"headers": {
            "X-Claude-Code-Agent-Id": "agent-123", "x-claude-code-session-id": "shared-session",
        }, "body": {}})
        self.assertEqual(identity["stream_id"], "agent:agent-123")
        self.assertEqual(identity["confidence"], "high")

    def test_missing_agent_header_remains_unclassified_not_primary(self) -> None:
        identity = classify_request_stream({"headers": {"x-claude-code-session-id": "shared-session"}, "body": {}})
        self.assertEqual(identity["classification"], "unclassified")
        self.assertEqual(identity["confidence"], "none")


if __name__ == "__main__":
    unittest.main()
