"""Unit tests for RADULOV grounded engineering tools."""

import unittest
from unittest.mock import MagicMock

from radulov.tools import (
    FUNCTION_DECLARATIONS,
    _resolve_safe_path,
    collect_function_calls,
    dispatch_tool,
    function_to_declaration,
    list_directory,
    read_file,
    run_tests,
    search_code,
)


class TestRadulovTools(unittest.TestCase):
    """Test suite for repository inspection and execution tools."""

    def test_read_file_success(self):
        """Ensure read_file reads known file and formats line numbers."""
        output = read_file("README.md", max_lines=10)
        self.assertIn("1 | # RADULOV", output)
        self.assertNotIn("Error", output)

    def test_read_file_missing(self):
        """Ensure read_file returns error message on missing file."""
        output = read_file("non_existent_file_xyz.txt")
        self.assertIn("Error: File not found", output)

    def test_path_traversal_prevention(self):
        """Ensure path traversal attempts are blocked."""
        output = read_file("../../windows/system32/cmd.exe")
        self.assertIn("outside repository root", output)

    def test_list_directory_success(self):
        """Ensure list_directory shows files and omits ignored dirs."""
        output = list_directory(".", max_depth=2)
        self.assertIn("README.md", output)
        self.assertIn("main.py", output)
        self.assertNotIn(".git/", output)

    def test_search_code_found(self):
        """Ensure search_code finds known symbols across files."""
        output = search_code("DEFAULT_MODEL")
        self.assertIn("main.py", output)
        self.assertNotIn("No matches found", output)

    def test_search_code_not_found(self):
        """Ensure search_code handles non-existent terms gracefully."""
        query = "ZZZ_" + "NON_EXISTENT_KEYWORD_XYZ_999"
        output = search_code(query)
        self.assertIn("No matches found", output)


    @unittest.mock.patch("subprocess.run")
    def test_run_tests_success(self, mock_run):
        """Ensure run_tests formats test results cleanly without recursing."""
        mock_run.return_value = unittest.mock.MagicMock(
            returncode=0,
            stdout="Ran 5 tests in 0.010s\n\nOK\n",
            stderr="",
        )
        output = run_tests("tests", timeout_sec=15)
        self.assertIn("Test Suite Status: PASSED", output)
        self.assertIn("Ran 5 tests", output)
        mock_run.assert_called_once()

    def test_tool_definitions_includes_gemini_docs(self):
        """Ensure TOOL_DEFINITIONS contains search_gemini_docs, get_gemini_doc, list_skills, and read_skill."""
        from radulov.tools import (
            TOOL_DEFINITIONS,
            get_gemini_doc,
            list_skills,
            read_skill,
            search_gemini_docs,
        )
        self.assertIn(search_gemini_docs, TOOL_DEFINITIONS)
        self.assertIn(get_gemini_doc, TOOL_DEFINITIONS)
        self.assertIn(list_skills, TOOL_DEFINITIONS)
        self.assertIn(read_skill, TOOL_DEFINITIONS)


    def test_function_to_declaration_uses_signature_and_docstring(self):
        """Convert a Python tool into an Interactions function declaration."""
        declaration = function_to_declaration(read_file)
        self.assertEqual(declaration["type"], "function")
        self.assertEqual(declaration["name"], "read_file")
        self.assertIn("Read the content of a file", declaration["description"])
        self.assertEqual(declaration["parameters"]["type"], "object")
        self.assertIn("file_path", declaration["parameters"]["required"])
        self.assertNotIn("max_lines", declaration["parameters"]["required"])
        self.assertEqual(
            declaration["parameters"]["properties"]["max_lines"]["type"], "integer"
        )

    def test_function_declarations_cover_all_tools(self):
        """FUNCTION_DECLARATIONS must list every TOOL_DEFINITIONS callable."""
        from radulov.tools import TOOL_DEFINITIONS

        declared = {item["name"] for item in FUNCTION_DECLARATIONS}
        implemented = {func.__name__ for func in TOOL_DEFINITIONS}
        self.assertEqual(declared, implemented)

    def test_collect_function_calls_from_list_steps(self):
        """collect_function_calls reads function_call steps and ignores other types."""
        text_step = MagicMock()
        text_step.type = "model_output"
        call_step = MagicMock()
        call_step.type = "function_call"
        call_step.name = "search_code"
        call_step.id = "fc-9"
        call_step.arguments = {"query": "DEFAULT_MODEL"}

        interaction = MagicMock()
        interaction.steps = [text_step, call_step]
        calls = collect_function_calls(interaction)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "search_code")
        self.assertEqual(calls[0]["call_id"], "fc-9")
        self.assertEqual(calls[0]["arguments"]["query"], "DEFAULT_MODEL")

    def test_collect_function_calls_ignores_non_list_steps(self):
        """MagicMock interactions without real steps must not look like tool calls."""
        self.assertEqual(collect_function_calls(MagicMock()), [])

    def test_dispatch_tool_executes_and_reports_unknown(self):
        """dispatch_tool runs mapped functions and returns errors for unknown names."""
        output = dispatch_tool("read_file", {"file_path": "README.md", "max_lines": 1})
        self.assertIn("RADULOV", output)
        missing = dispatch_tool("not_a_real_tool", {})
        self.assertIn("Unknown tool", missing)


if __name__ == "__main__":
    unittest.main()
