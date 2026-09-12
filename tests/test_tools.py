"""Unit tests for RADULOV grounded engineering tools."""

import unittest
from radulov.tools import (
    _resolve_safe_path,
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



if __name__ == "__main__":
    unittest.main()
