from __future__ import annotations

import json
import unittest

from src.server.codex_responses import parse_codex_message


class CodexResponsesTests(unittest.TestCase):
    def test_extracts_create_fields_without_claiming_full_context(self) -> None:
        raw = json.dumps({
            "type": "response.create",
            "model": "codex-model",
            "instructions": "Follow the project rules.",
            "input": [{"role": "user", "content": "hello"}],
            "previous_response_id": "resp-prior",
            "tools": [{"type": "function", "name": "lookup"}],
        })
        parsed = parse_codex_message("client_to_server", raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["observation"], "response.create")
        self.assertEqual(parsed["request"]["previous_response_id"], "resp-prior")
        self.assertEqual(parsed["request_completeness"], "wire_message_fields_only")

    def test_extracts_usage_without_double_counting_cached_or_reasoning_tokens(self) -> None:
        raw = json.dumps({
            "type": "response.completed",
            "response": {
                "id": "resp-1", "model": "codex-model",
                "usage": {
                    "input_tokens": 120, "output_tokens": 30, "total_tokens": 150,
                    "input_tokens_details": {"cached_tokens": 80},
                    "output_tokens_details": {"reasoning_tokens": 10},
                },
            },
        })
        parsed = parse_codex_message("server_to_client", raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["usage"], {
            "input_tokens": 120, "cached_input_tokens": 80,
            "uncached_input_tokens": 40, "output_tokens": 30,
            "reasoning_output_tokens": 10, "total_tokens": 150,
        })
        self.assertIsNone(parsed["context_window_tokens"])
        self.assertEqual(parsed["context_window_source"], "unknown")

    def test_abstains_on_unrecognized_direction_shape_and_invalid_counts(self) -> None:
        self.assertIsNone(parse_codex_message("server_to_client", b"\x00\xff"))
        self.assertIsNone(parse_codex_message("server_to_client", '{"type":"response.created"}'))
        self.assertIsNone(parse_codex_message("client_to_server", '{"type":"response.completed"}'))
        parsed = parse_codex_message("server_to_client", json.dumps({
            "type": "response.completed",
            "response": {"usage": {"input_tokens": True, "input_tokens_details": {"cached_tokens": 100}}},
        }))
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertIsNone(parsed["usage"]["input_tokens"])
        self.assertIsNone(parsed["usage"]["uncached_input_tokens"])


if __name__ == "__main__":
    unittest.main()
