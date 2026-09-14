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
    _new_session_file,
    execute_interaction,
    format_file_context,
    handle_chat_command,
    load_system_instruction,
    parse_args,
    run_chat_loop,
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
            self.assertIsNone(args.cli_gemini_docs)
            self.assertFalse(args.cli_list_skills)
            self.assertIsNone(args.cli_read_skill)

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

    def test_parse_args_gemini_docs(self):
        """Ensure --docs / --gemini-docs sets cli_gemini_docs."""
        with patch("sys.argv", ["main.py", "--docs", "interactions streaming"]):
            args = parse_args()
            self.assertEqual(args.cli_gemini_docs, "interactions streaming")

    def test_parse_args_skills(self):
        """Ensure --skills and --skill arguments are parsed correctly."""
        with patch("sys.argv", ["main.py", "--skills"]):
            args = parse_args()
            self.assertTrue(args.cli_list_skills)

        with patch("sys.argv", ["main.py", "--skill", "gemini-api-dev"]):
            args = parse_args()
            self.assertEqual(args.cli_read_skill, "gemini-api-dev")


    def test_load_system_instruction_missing_file(self):
        """Ensure load_system_instruction raises FileNotFoundError on missing file."""
        with self.assertRaises(FileNotFoundError):
            load_system_instruction(Path("non_existent_prompt.md"))

    def test_format_file_context(self):
        """Ensure format_file_context reads repo files and refuses paths outside the root."""
        sample = Path("tests") / "_tmp_format_file_context.txt"
        sample.write_text("print('hello')\n", encoding="utf-8")
        try:
            with patch("sys.stderr"):
                context = format_file_context([str(sample), "non_existent_file.xyz"])
                outside = format_file_context(["/etc/passwd"])
            self.assertIn("--- BEGIN FILE: tests/_tmp_format_file_context.txt ---", context)
            self.assertIn("print('hello')", context)
            self.assertIn("--- END FILE: tests/_tmp_format_file_context.txt ---", context)
            self.assertEqual(outside, "")
        finally:
            sample.unlink(missing_ok=True)


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

    def test_execute_interaction_streaming_runs_tools_from_step_start(self):
        """Streaming completed payloads may omit steps; collect function_call from step.start."""
        mock_client = MagicMock()

        start = MagicMock()
        start.event_type = "step.start"
        start.step.type = "function_call"
        start.step.name = "read_file"
        start.step.id = "call_readme"
        start.step.arguments = {"file_path": "README.md", "max_lines": 2}

        completed = MagicMock()
        completed.event_type = "interaction.completed"
        completed.interaction.id = "int-stream-1"
        completed.interaction.steps = None

        follow_delta = MagicMock()
        follow_delta.event_type = "step.delta"
        follow_delta.delta.type = "text"
        follow_delta.delta.text = "README starts with RADULOV"

        follow_done = MagicMock()
        follow_done.event_type = "interaction.completed"
        follow_done.interaction.id = "int-stream-2"
        follow_done.interaction.steps = []

        mock_client.interactions.create.side_effect = [
            [start, completed],
            [follow_delta, follow_done],
        ]

        with patch("builtins.print"), patch("sys.stderr"):
            text, int_id = execute_interaction(
                client=mock_client,
                model="models/gemini-3.8-flash",
                user_input="What is the README title?",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=True,
            )

        self.assertEqual(text, "README starts with RADULOV")
        self.assertEqual(int_id, "int-stream-2")
        self.assertEqual(mock_client.interactions.create.call_count, 2)
        follow_kwargs = mock_client.interactions.create.call_args_list[1].kwargs
        self.assertEqual(follow_kwargs["previous_interaction_id"], "int-stream-1")
        self.assertEqual(follow_kwargs["input"][0]["type"], "function_result")
        self.assertIn("RADULOV", follow_kwargs["input"][0]["result"][0]["text"])

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

    def test_execute_interaction_sync_runs_tools_then_continues(self):
        """Execute function_call steps locally and send function_result back."""
        mock_client = MagicMock()

        function_call = MagicMock()
        function_call.type = "function_call"
        function_call.name = "read_file"
        function_call.id = "call_readme"
        function_call.arguments = {"file_path": "README.md", "max_lines": 2}

        first = MagicMock()
        first.output_text = ""
        first.id = "int-tool-1"
        first.steps = [function_call]

        second = MagicMock()
        second.output_text = "README starts with RADULOV"
        second.id = "int-tool-2"
        second.steps = []

        mock_client.interactions.create.side_effect = [first, second]

        with patch("builtins.print"), patch("sys.stderr"):
            text, int_id = execute_interaction(
                client=mock_client,
                model="models/gemini-3.8-flash",
                user_input="What is the README title?",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 1024},
                stream=False,
            )

        self.assertEqual(text, "README starts with RADULOV")
        self.assertEqual(int_id, "int-tool-2")
        self.assertEqual(mock_client.interactions.create.call_count, 2)

        first_kwargs = mock_client.interactions.create.call_args_list[0].kwargs
        self.assertTrue(first_kwargs["tools"])
        self.assertIsInstance(first_kwargs["tools"][0], dict)
        self.assertEqual(first_kwargs["tools"][0]["type"], "function")

        follow_up = mock_client.interactions.create.call_args_list[1].kwargs
        self.assertEqual(follow_up["previous_interaction_id"], "int-tool-1")
        payload = follow_up["input"]
        self.assertEqual(payload[0]["type"], "function_result")
        self.assertEqual(payload[0]["name"], "read_file")
        self.assertEqual(payload[0]["call_id"], "call_readme")
        self.assertIn("RADULOV", payload[0]["result"][0]["text"])

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

    def test_bare_slash_commands_show_usage_not_model(self):
        """Bare slash commands must be consumed locally with usage text."""
        session = {
            "previous_interaction_id": "keep-me",
            "turn": 3,
            "session_file": Path("unused.jsonl"),
            "should_exit": False,
        }
        attached: list[str] = []
        client = MagicMock()
        for command, needle in (
            ("/build", "Usage: /build"),
            ("/docs", "Usage: /docs"),
            ("/file", "Usage: /file"),
            ("/skill", "Usage: /skill"),
            ("/read", "Usage: /read"),
            ("/grep", "Usage: /grep"),
            ("/doc", "Usage: /doc"),
        ):
            with patch("builtins.print") as mock_print:
                handled = handle_chat_command(
                    command,
                    client=client,
                    model="models/gemini-3.8-flash",
                    attached_files=attached,
                    session=session,
                )
            self.assertTrue(handled, command)
            printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
            self.assertIn(needle, printed)
        self.assertEqual(session["previous_interaction_id"], "keep-me")
        self.assertFalse(session["should_exit"])
        client.interactions.create.assert_not_called()

    def test_unknown_slash_command_not_sent_to_model(self):
        """Unknown slash commands stay in the REPL and never reach Gemini."""
        session = {
            "previous_interaction_id": None,
            "turn": 0,
            "session_file": Path("unused.jsonl"),
            "should_exit": False,
        }
        with patch("builtins.print") as mock_print:
            handled = handle_chat_command(
                "/not-a-real-command",
                client=MagicMock(),
                model="models/gemini-3.8-flash",
                attached_files=[],
                session=session,
            )
        self.assertTrue(handled)
        printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertIn("Unknown command", printed)

    def test_clear_rotates_session_transcript(self):
        """/clear must reset turn state and point at a new session JSONL path."""
        original = _new_session_file()
        session = {
            "previous_interaction_id": "int-old",
            "turn": 4,
            "session_file": original,
            "should_exit": False,
        }
        attached = ["README.md"]
        with patch("builtins.print"):
            handled = handle_chat_command(
                "/clear",
                client=MagicMock(),
                model="models/gemini-3.8-flash",
                attached_files=attached,
                session=session,
            )
        self.assertTrue(handled)
        self.assertIsNone(session["previous_interaction_id"])
        self.assertEqual(session["turn"], 0)
        self.assertEqual(attached, [])
        self.assertNotEqual(session["session_file"], original)
        self.assertTrue(str(session["session_file"]).endswith(".jsonl"))

    def test_chat_loop_keyboard_interrupt_during_generation_preserves_session(self):
        """Ctrl+C mid-generation must not kill the REPL or advance the turn counter."""
        inputs = iter(["hello", "/history", "/exit"])

        def _fake_input(_prompt: str = "") -> str:
            return next(inputs)

        with (
            patch("builtins.input", side_effect=_fake_input),
            patch("builtins.print") as mock_print,
            patch(
                "main.execute_interaction",
                side_effect=KeyboardInterrupt(),
            ) as mock_execute,
            patch("main._new_session_file", return_value=Path("session_test.jsonl")),
        ):
            code = run_chat_loop(
                client=MagicMock(),
                model="models/gemini-3.8-flash",
                system_instruction="Prompt",
                generation_config={"max_output_tokens": 128},
                initial_files=[],
                stream=True,
                enable_tools=False,
            )

        self.assertEqual(code, 0)
        self.assertEqual(mock_execute.call_count, 1)
        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn("Generation interrupted", printed)
        self.assertIn("Total turns: 0", printed)


if __name__ == "__main__":
    unittest.main()
