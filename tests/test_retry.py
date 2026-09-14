"""Unit tests for Gemini generate_content retry and builder write accounting."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from radulov.builder import execute_autonomous_build
from radulov.retry import generate_content_with_retry, is_retryable_gemini_error
from radulov.synthesizer import synthesize_dual_options


class FakeAPIError(Exception):
    def __init__(self, code: int, status: str = "UNAVAILABLE") -> None:
        super().__init__(f"{code} {status}.")
        self.code = code
        self.status = status


class TestGeminiRetry(unittest.TestCase):
    """Transient Gemini 503 failures should retry; quota/client errors should not."""

    def test_is_retryable_for_503_unavailable(self):
        self.assertTrue(is_retryable_gemini_error(FakeAPIError(503, "UNAVAILABLE")))
        self.assertTrue(is_retryable_gemini_error(Exception("503 UNAVAILABLE")))
        self.assertFalse(is_retryable_gemini_error(FakeAPIError(429, "RESOURCE_EXHAUSTED")))
        self.assertFalse(is_retryable_gemini_error(FakeAPIError(400, "INVALID_ARGUMENT")))

    def test_generate_content_retries_503_then_succeeds(self):
        client = MagicMock()
        ok = MagicMock()
        ok.text = '{"ok": true}'
        client.models.generate_content.side_effect = [
            FakeAPIError(503, "UNAVAILABLE"),
            ok,
        ]
        sleeps: list[float] = []
        result = generate_content_with_retry(
            client,
            max_attempts=3,
            backoff_sec=0.5,
            sleeper=sleeps.append,
            model="models/gemini-3.8-flash",
            contents="prompt",
        )
        self.assertIs(result, ok)
        self.assertEqual(client.models.generate_content.call_count, 2)
        self.assertEqual(sleeps, [0.5])

    def test_generate_content_does_not_retry_quota_errors(self):
        client = MagicMock()
        client.models.generate_content.side_effect = FakeAPIError(
            429, "RESOURCE_EXHAUSTED"
        )
        with self.assertRaises(FakeAPIError):
            generate_content_with_retry(
                client,
                max_attempts=3,
                sleeper=lambda _delay: None,
                model="models/gemini-3.8-flash",
                contents="prompt",
            )
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_synthesize_dual_options_retries_unavailable(self):
        client = MagicMock()
        ok = MagicMock()
        ok.text = json.dumps(
            {
                "user_intent_summary": "Add echo",
                "option_a": {"title": "A"},
                "option_b": {"title": "B"},
            }
        )
        client.models.generate_content.side_effect = [
            FakeAPIError(503, "UNAVAILABLE"),
            ok,
        ]
        with patch("radulov.retry.time.sleep"):
            result = synthesize_dual_options(
                client, "goal", "summary", "research"
            )
        self.assertEqual(result["option_a"]["title"], "A")
        self.assertEqual(client.models.generate_content.call_count, 2)


class TestBuilderWriteAccounting(unittest.TestCase):
    """Repair loops must keep the original generated file list."""

    def test_execute_autonomous_build_accumulates_written_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tests").mkdir()
            first = MagicMock()
            first.text = json.dumps(
                {
                    "files": [
                        {"path": "examples/a.py", "content": "x = 1\n"},
                        {
                            "path": "tests/test_a.py",
                            "content": (
                                "import unittest\n"
                                "class T(unittest.TestCase):\n"
                                "    def test_ok(self):\n"
                                "        self.assertTrue(True)\n"
                            ),
                        },
                    ],
                    "build_notes": "initial",
                }
            )
            repair = MagicMock()
            repair.text = json.dumps(
                {
                    "files": [
                        {
                            "path": "tests/test_a.py",
                            "content": (
                                "import unittest\n"
                                "class T(unittest.TestCase):\n"
                                "    def test_ok(self):\n"
                                "        self.assertTrue(True)\n"
                            ),
                        }
                    ],
                    "build_notes": "repair",
                }
            )
            client = MagicMock()
            client.models.generate_content.side_effect = [first, repair]
            fail = "Test Suite Status: FAILED (exit code 1)\n"
            passed = "Test Suite Status: PASSED\n"
            with patch(
                "radulov.builder._run_unittest", side_effect=[fail, passed]
            ), patch("builtins.print"):
                result = execute_autonomous_build(
                    client,
                    {"title": "Option A"},
                    "goal",
                    "summary",
                    repo_root=root,
                )

            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["repair_attempts"], 1)
            self.assertEqual(
                result["written_files"],
                ["examples/a.py", "tests/test_a.py"],
            )


if __name__ == "__main__":
    unittest.main()
