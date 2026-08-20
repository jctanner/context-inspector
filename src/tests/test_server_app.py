from __future__ import annotations

import unittest

from src.server.app import apply_terminal_message, create_app
from src.server.config import Settings


class FakeSession:
    def __init__(self) -> None:
        self.inputs: list[bytes] = []
        self.sizes: list[tuple[int, int]] = []

    def write(self, data: bytes) -> None:
        self.inputs.append(data)

    def resize(self, rows: int, cols: int) -> None:
        if rows < 2 or cols < 2:
            raise ValueError("terminal dimensions must be at least 2")
        self.sizes.append((rows, cols))


class ServerAppTests(unittest.TestCase):
    def test_input_is_encoded_without_shell_or_line_transformation(self) -> None:
        session = FakeSession()
        self.assertIsNone(apply_terminal_message(session, {"type": "input", "data": "hello\r\x1b[A"}))
        self.assertEqual(session.inputs, [b"hello\r\x1b[A"])

    def test_resize_is_applied(self) -> None:
        session = FakeSession()
        self.assertIsNone(apply_terminal_message(session, {"type": "resize", "rows": 44, "cols": 150}))
        self.assertEqual(session.sizes, [(44, 150)])

    def test_invalid_control_messages_return_safe_errors(self) -> None:
        session = FakeSession()
        self.assertEqual(apply_terminal_message(session, {"type": "input", "data": 7}), "input.data must be a string")
        self.assertEqual(apply_terminal_message(session, {"type": "resize", "rows": 0, "cols": 80}), "terminal dimensions must be at least 2")
        self.assertEqual(apply_terminal_message(session, {"type": "unknown"}), "unsupported terminal message")

    def test_application_routes_are_registered(self) -> None:
        app = create_app(settings=Settings())
        paths = {route.path for route in app.routes}
        self.assertIn("/api/sessions", paths)
        self.assertIn("/api/sessions/{session_id}", paths)
        self.assertIn("/api/sessions/{session_id}/terminal", paths)
        self.assertIn("/api/sessions/{session_id}/flows", paths)
        self.assertIn("/api/sessions/{session_id}/contexts", paths)


if __name__ == "__main__":
    unittest.main()
