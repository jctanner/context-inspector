import unittest
from src.diagnostics.correlate_transcripts import identifier_index, join_scope


class TranscriptCorrelationTests(unittest.TestCase):
    def test_duplicate_streamed_entries_deduplicate_but_cross_scope_collisions_remain(self):
        rows = [{"message_id": "a", "scope": "main"}] * 3
        rows += [{"message_id": "a", "scope": "subagent:test"}, {"scope": "main"}]
        self.assertEqual(identifier_index(rows, "message_id"), {"a": {"main", "subagent:test"}})

    def test_exact_agreement_and_missing_evidence(self):
        self.assertEqual(join_scope({"main"}, {"main"}), "exact_main")
        self.assertEqual(join_scope(set(), {"subagent:test"}), "exact_subagent")
        self.assertEqual(join_scope(set(), set()), "unmatched")

    def test_conflicting_and_ambiguous_identifiers_are_not_attributed(self):
        self.assertEqual(join_scope({"main"}, {"subagent:test"}), "conflicting_identifiers")
        self.assertEqual(join_scope({"main", "subagent:test"}, set()), "ambiguous_scope")
