"""Tests for RADULOV main runner and repository integrity."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_THINKING_LEVEL,
    PROMPT_FILE,
    execute_interaction,
    load_system_instruction,
    parse_args,
)


class TestRadulovCore(unittest.TestCase):
    """Integrity and functionality tests for the RADULOV runner."""

    def test_prompt_file_exists_and_valid(self):
        """Ensure system prompt markdown file exists and contains expected header."""
        self.assertTrue(PROMPT_FILE.is_file(), f"Missing prompt file at {PROMPT_FILE}")
        content = load_system_instruction(PROMPT_FILE)
        self.assertIn("RADULOV — Aegis System Prompt", content)
        self.assertIn("You are Aegis", content)

    def test_parse_args_defaults(self):
        """Ensure default CLI arguments are populated correctly."""
        with patch("sys.argv", ["main.py"]):
            args = parse_args()
            self.assertEqual(args.model, DEFAULT_MODEL)
            self.assertIsNone(args.user_input)
            self.assertEqual(args.thinking_level, DEFAULT_THINKING_LEVEL)
            self.assertEqual(args.max_tokens, DEFAULT_MAX_TOKENS)
            self.assertTrue(args.stream)

    def test_parse_args_custom(self):
        """Ensure custom model, thinking level, token budget, and stream flags work."""
        custom_input = "Audit access control."
        custom_model = "models/gemini-3.1-pro-preview"
        with patch(
            "sys.argv",
            [
                "main.py",
                "-m",
                custom_model,
                "-i",
                custom_input,
                "--thinking-level",
                "high",
                "--max-tokens",
                "32768",
                "--no-stream",
            ],
        ):
            args = parse_args()
            self.assertEqual(args.model, custom_model)
            self.assertEqual(args.user_input, custom_input)
            self.assertEqual(args.thinking_level, "high")
            self.assertEqual(args.max_tokens, 32768)
            self.assertFalse(args.stream)

    def test_load_system_instruction_missing_file(self):
        """Ensure load_system_instruction raises FileNotFoundError on missing file."""
        with self.assertRaises(FileNotFoundError):
            load_system_instruction(Path("non_existent_prompt.md"))

    def test_execute_interaction_streaming(self):
        """Ensure streaming events are correctly unpacked and printed."""
        mock_client = MagicMock()

        event1 = MagicMock()
        event1.event_type = "step.delta"
        event1.delta.type = "text"
        event1.delta.text = "Hello "

        event2 = MagicMock()
        event2.event_type = "step.delta"
        event2.delta.type = "text"
        event2.delta.text = "world!"

        event3 = MagicMock()
        event3.event_type = "interaction.completed"

        mock_client.interactions.create.return_value = [event1, event2, event3]

        with patch("builtins.print") as mock_print:
            execute_interaction(
                client=mock_client,
                model="models/gemini-3.7-flash",
                user_input="Test",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=True,
            )
            mock_print.assert_any_call("Hello ", end="", flush=True)
            mock_print.assert_any_call("world!", end="", flush=True)

    def test_execute_interaction_sync(self):
        """Ensure synchronous interaction mode outputs text directly."""
        mock_client = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.output_text = "Synchronous response text"
        mock_client.interactions.create.return_value = mock_interaction

        with patch("builtins.print") as mock_print:
            execute_interaction(
                client=mock_client,
                model="models/gemini-3.7-flash",
                user_input="Test",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=False,
            )
            mock_print.assert_called_with("Synchronous response text")


if __name__ == "__main__":
    unittest.main()
