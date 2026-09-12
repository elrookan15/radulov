"""Tests for RADULOV main runner and repository integrity."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from main import DEFAULT_MODEL, PROMPT_FILE, load_system_instruction, parse_args


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

    def test_parse_args_custom(self):
        """Ensure custom model and prompt inputs are captured."""
        custom_input = "Audit access control."
        custom_model = "models/gemini-2.5-pro"
        with patch("sys.argv", ["main.py", "-m", custom_model, "-i", custom_input]):
            args = parse_args()
            self.assertEqual(args.model, custom_model)
            self.assertEqual(args.user_input, custom_input)

    def test_load_system_instruction_missing_file(self):
        """Ensure load_system_instruction raises FileNotFoundError on missing file."""
        with self.assertRaises(FileNotFoundError):
            load_system_instruction(Path("non_existent_prompt.md"))


if __name__ == "__main__":
    unittest.main()
