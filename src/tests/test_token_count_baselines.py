import unittest
from src.server.context import classify_request_operation, derive_context_diffs
from src.tests.test_context_diff import request_event


class TokenCountBaselineTests(unittest.TestCase):
    def test_nonstreaming_probe_does_not_replace_streaming_baseline(self):
        first = request_event(1, {"messages": [{"role": "user", "content": "first"}]})
        first["payload"]["request"]["url"] = "https://vertex.example/models/model:streamRawPredict"
        probe = request_event(2, {"messages": [{"role": "user", "content": "probe"}]})
        probe["payload"]["request"]["url"] = "https://vertex.example/models/model:rawPredict"
        next_turn = request_event(3, {"messages": [{"role": "user", "content": "next"}]})
        next_turn["payload"]["request"]["url"] = first["payload"]["request"]["url"]
        self.assertEqual(derive_context_diffs([first, probe, next_turn])[-1]["predecessor_flow_id"], "flow-1")

    def test_different_origins_are_not_positional_transformations(self):
        first = request_event(1, {"messages": [{"role": "user", "content": "foo"}]})
        second = request_event(2, {"messages": [{"role": "user", "content": "<system-reminder>context</system-reminder>"}]})
        d = derive_context_diffs([first, second])[-1]
        self.assertEqual(d["counts"], {"added": 1, "removed": 1, "retained": 0, "transformed": 0})

    def test_endpoint_detection_is_not_based_on_prompt_or_query(self):
        for url in ["https://api.anthropic.com/v1/messages/count_tokens", "https://region.googleapis.com/v1/projects/p/locations/l/publishers/anthropic/models/count-tokens:rawPredict?x=1"]:
            self.assertEqual(classify_request_operation({"method": "POST", "url": url}), "token_count")
            self.assertEqual(classify_request_operation({"method": "GET", "url": url}), "unknown")
        self.assertEqual(classify_request_operation({"method": "POST", "url": "https://api.anthropic.com/v1/messages?next=/messages/count_tokens"}), "unknown")

    def test_counting_never_replaces_generation_baseline_and_numbers_preserved(self):
        first = request_event(1, {"messages": [{"role": "user", "content": "<system-reminder>context</system-reminder>"}]})
        counter = request_event(2, {"messages": [{"role": "user", "content": "foo"}]})
        counter["payload"]["request"]["url"] = "https://vertex.example/models/count-tokens:rawPredict"
        next_turn = request_event(3, {"messages": [{"role": "user", "content": "<system-reminder>context</system-reminder>"}, {"role": "user", "content": "next"}]})
        repeat_count = request_event(4, {"messages": [{"role": "user", "content": "bar"}]})
        repeat_count["payload"]["request"]["url"] = counter["payload"]["request"]["url"]
        diffs = derive_context_diffs([first, counter, next_turn, repeat_count])
        self.assertEqual(len(diffs), 4)
        self.assertIsNone(diffs[1]["predecessor_flow_id"])
        self.assertEqual(diffs[2]["predecessor_flow_id"], "flow-1")
        self.assertEqual(diffs[2]["counts"]["transformed"], 0)
        self.assertEqual(diffs[3]["predecessor_flow_id"], "flow-2")
        self.assertEqual(diffs[1]["request_operation"], "token_count")
        self.assertEqual(diffs[2]["predecessor_confidence"], "none")
