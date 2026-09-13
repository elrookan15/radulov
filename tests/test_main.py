"""Tests for RADULOV main runner and repository integrity."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_THINKING_LEVEL,
    PROMPT_FILE,
    execute_interaction,
    format_file_context,
    load_system_instruction,
    parse_args,
    save_session_turn,
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
            self.assertEqual(args.files, [])
            self.assertFalse(args.chat)
            self.assertIsNone(args.build_goal)

    def test_parse_args_custom(self):
        """Ensure custom model, thinking level, files, and chat flags work."""
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
                "-b",
                "Build auth system",
                "-f",
                "main.py",
                "-f",
                "README.md",
                "--chat",
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
            self.assertEqual(args.build_goal, "Build auth system")
            self.assertEqual(args.files, ["main.py", "README.md"])
            self.assertTrue(args.chat)
            self.assertEqual(args.thinking_level, "high")
            self.assertEqual(args.max_tokens, 32768)
            self.assertFalse(args.stream)


    def test_load_system_instruction_missing_file(self):
        """Ensure load_system_instruction raises FileNotFoundError on missing file."""
        with self.assertRaises(FileNotFoundError):
            load_system_instruction(Path("non_existent_prompt.md"))

    def test_format_file_context(self):
        """Ensure format_file_context reads and demarcates local files correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("print('hello')\n")
            f1_path = Path(f1.name)

        try:
            with patch("sys.stderr"):
                context = format_file_context([f1_path, "non_existent_file.xyz"])
            self.assertIn(f"--- BEGIN FILE: {f1_path.as_posix()} ---", context)
            self.assertIn("print('hello')", context)
            self.assertIn(f"--- END FILE: {f1_path.as_posix()} ---", context)
        finally:
            if f1_path.exists():
                f1_path.unlink()


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
        event3.interaction.id = "int-12345"

        mock_client.interactions.create.return_value = [event1, event2, event3]

        with patch("builtins.print") as mock_print:
            text, int_id = execute_interaction(
                client=mock_client,
                model="models/gemini-3.7-flash",
                user_input="Test",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=True,
                previous_interaction_id="prev-001",
            )
            self.assertEqual(text, "Hello world!")
            self.assertEqual(int_id, "int-12345")
            mock_print.assert_any_call("Hello ", end="", flush=True)
            mock_print.assert_any_call("world!", end="", flush=True)

            # Check that previous_interaction_id was passed
            call_kwargs = mock_client.interactions.create.call_args[1]
            self.assertEqual(call_kwargs["previous_interaction_id"], "prev-001")

    def test_execute_interaction_sync(self):
        """Ensure synchronous interaction mode outputs text directly."""
        mock_client = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.output_text = "Synchronous response text"
        mock_interaction.id = "int-sync-99"
        mock_client.interactions.create.return_value = mock_interaction

        with patch("builtins.print") as mock_print:
            text, int_id = execute_interaction(
                client=mock_client,
                model="models/gemini-3.7-flash",
                user_input="Test",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=False,
            )
            self.assertEqual(text, "Synchronous response text")
            self.assertEqual(int_id, "int-sync-99")
            mock_print.assert_called_with("Synchronous response text")

    def test_save_session_turn(self):
        """Ensure session turn logs are correctly appended to JSONL file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_path = Path(f.name)

        try:
            save_session_turn(
                session_file=session_path,
                turn=1,
                user_input="Design DB schema",
                model_output="PostgreSQL with RLS",
                interaction_id="int-abc-123",
            )
            content = session_path.read_text(encoding="utf-8").strip()
            record = json.loads(content)
            self.assertEqual(record["turn"], 1)
            self.assertEqual(record["user_input"], "Design DB schema")
            self.assertEqual(record["model_output"], "PostgreSQL with RLS")
            self.assertEqual(record["interaction_id"], "int-abc-123")
        finally:
            if session_path.exists():
                session_path.unlink()


if __name__ == "__main__":
    unittest.main()
