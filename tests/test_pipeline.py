"""Unit tests for RADULOV scanner, synthesizer, and autonomous builder."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from radulov.builder import _extract_builder_json, _write_files_to_disk
from radulov.researcher import conduct_deep_research
from radulov.scanner import format_scan_summary, scan_repository
from radulov.synthesizer import _extract_json, format_options_card
from radulov.tools import _run_unittest


class TestRadulovPipeline(unittest.TestCase):
    """Test suite for research, synthesis, and construction components."""

    def test_scan_repository(self):
        """Ensure scanner identifies repository files, languages, and manifests."""
        scan_data = scan_repository(".")
        self.assertIn("Python", scan_data["detected_languages"])
        self.assertIn("pyproject.toml", scan_data["manifests"])
        self.assertGreater(scan_data["total_files"], 0)

        summary = format_scan_summary(scan_data)
        self.assertIn("REPOSITORY TOPOLOGY", summary)
        self.assertIn("Primary Languages", summary)

    def test_extract_json_clean(self):
        """Ensure _extract_json parses clean JSON and markdown-fenced JSON."""
        clean = '{"status": "ok", "count": 42}'
        self.assertEqual(_extract_json(clean), {"status": "ok", "count": 42})

        fenced = '```json\n{"status": "ok", "count": 42}\n```'
        self.assertEqual(_extract_json(fenced), {"status": "ok", "count": 42})

    def test_format_options_card(self):
        """Ensure format_options_card renders structured comparison cards."""
        options_data = {
            "user_intent_summary": "Add authentication",
            "option_a": {
                "title": "Option A: JWT Native",
                "philosophy": "Zero dependencies",
                "tech_stack": ["python-jose"],
                "files_to_create_or_modify": ["auth.py"],
                "architecture_summary": "Stateless JWT tokens",
                "pros": ["Fast", "Simple"],
                "cons": ["No instant revocation"],
                "estimated_bundle_or_memory_delta": "0 KB",
            },
            "option_b": {
                "title": "Option B: Supabase Auth Suite",
                "philosophy": "Full OAuth & RLS",
                "tech_stack": ["@supabase/supabase-js"],
                "files_to_create_or_modify": ["auth.py", "middleware.py"],
                "architecture_summary": "Enterprise OAuth with RLS",
                "pros": ["MFA", "OAuth2"],
                "cons": ["External dependency"],
                "estimated_bundle_or_memory_delta": "+12 KB",
            },
        }
        card = format_options_card(options_data)
        self.assertIn("OPTION A: JWT NATIVE", card)
        self.assertIn("OPTION B: SUPABASE AUTH SUITE", card)
        self.assertIn("Zero dependencies", card)

    def test_write_files_to_disk_safe(self):
        """Ensure builder writes files only within target root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            files_to_write = [
                {"path": "src/module.py", "content": "x = 10\n"},
                {"path": "tests/test_module.py", "content": "def test_x(): pass\n"},
            ]
            written = _write_files_to_disk(files_to_write, tmp_root)
            self.assertEqual(len(written), 2)
            self.assertTrue((tmp_root / "src" / "module.py").is_file())
            self.assertEqual((tmp_root / "src" / "module.py").read_text(), "x = 10\n")

    def test_write_files_to_disk_blocks_traversal_and_secrets(self):
        """Ensure builder refuses path traversal and sensitive credential files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            files_to_write = [
                {"path": "../escape.py", "content": "should_not_write = True\n"},
                {"path": ".env", "content": "GEMINI_API_KEY=leaked\n"},
                {"path": ".git/config", "content": "[core]\n"},
                {"path": "secrets/api.pem", "content": "PRIVATE KEY\n"},
                {"path": "id_rsa", "content": "ssh-key\n"},
                {"path": "keys/credentials.json", "content": "{}\n"},
            ]
            with patch("sys.stderr"):
                written = _write_files_to_disk(files_to_write, tmp_root)
            self.assertEqual(written, [])
            self.assertFalse((tmp_root / ".env").exists())
            self.assertFalse((tmp_root / ".git" / "config").exists())
            self.assertFalse((tmp_root / "secrets" / "api.pem").exists())
            self.assertFalse((tmp_root / "id_rsa").exists())
            self.assertFalse((tmp_root / "keys" / "credentials.json").exists())
            self.assertFalse((tmp_root.parent / "escape.py").exists())

    def test_research_timeout_returns_without_waiting_on_worker(self):
        """Ensure the 120s research cap returns even if the worker is still running."""

        def _hang(_client, _prompt, _model):
            time.sleep(0.6)
            return "late research"

        with patch("radulov.researcher._invoke_research", side_effect=_hang):
            started = time.monotonic()
            result = conduct_deep_research(
                client=MagicMock(),
                user_goal="Add auth",
                codebase_summary="Python CLI",
                timeout_sec=0.2,
            )
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.5)
        self.assertIn("timed out", result.lower())

    def test_run_unittest_uses_target_root(self):
        """Builder verification must run tests in the write root, not the package root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            tests_dir = tmp_root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_generated.py").write_text(
                "import unittest\n"
                "class TestGenerated(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output = _run_unittest(tmp_root, "tests", timeout_sec=15)
            self.assertIn("Test Suite Status: PASSED", output)
            self.assertIn("test_ok", output)


if __name__ == "__main__":
    unittest.main()
