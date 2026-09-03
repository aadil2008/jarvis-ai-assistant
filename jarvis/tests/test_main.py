from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


class CommandTests(unittest.TestCase):
    def test_polite_open_command_stays_local(self) -> None:
        self.assertEqual(main.parse_local_intent("Jarvis, can you open Safari for me?"), ("open", "Safari"))

    def test_calendar_request_stays_local(self) -> None:
        self.assertEqual(main.parse_local_intent("look at my calendar"), ("calendar", ""))

    def test_general_question_goes_to_router(self) -> None:
        self.assertEqual(
            main.parse_local_intent("What is the future of artificial intelligence?"),
            ("chat", "What is the future of artificial intelligence?"),
        )

    def test_spoken_output_hides_code(self) -> None:
        output = main.text_for_speech("Here it is.\n```python\nprint('hello')\n```")
        self.assertNotIn("print", output)
        self.assertIn("displayed the code", output)


if __name__ == "__main__":
    unittest.main()
