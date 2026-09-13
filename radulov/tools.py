"""Grounded Engineering Tools for RADULOV Aegis Intelligence.

Provides deterministic, read-only repository inspection and test runner tools
to ensure Aegis never hallucinates execution evidence or file contents.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 512 * 1024  # 512 KB
SEARCH_FILE_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".example",
}
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".radulov", "archive"}


def _resolve_safe_path(target_path: str | Path) -> Path:
    """Resolve and validate that the target path stays within the repository root."""
    resolved = (REPO_ROOT / target_path).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        raise PermissionError(f"Access denied: '{target_path}' is outside repository root.")
    return resolved


def read_file(file_path: str, max_lines: int = 1000) -> str:
    """Read the content of a file within the repository.

    Args:
        file_path: Relative path to the file from repository root.
        max_lines: Maximum number of lines to return.

    Returns:
        The content of the file with line numbers, or an error message.
    """
    try:
        path = _resolve_safe_path(file_path)
        if not path.is_file():
            return f"Error: File not found: '{file_path}'"

        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            return (
                f"Error: File '{file_path}' exceeds safety limit "
                f"({size} bytes > {MAX_FILE_BYTES} bytes)."
            )

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        truncated = len(lines) > max_lines
        selected_lines = lines[:max_lines]

        formatted = [f"{idx + 1:4d} | {line}" for idx, line in enumerate(selected_lines)]
        output = "\n".join(formatted)
        if truncated:
            output += f"\n... [Truncated: showing first {max_lines} of {len(lines)} lines]"
        return output
    except Exception as err:
        return f"Error reading file '{file_path}': {err}"


def list_directory(dir_path: str = ".", max_depth: int = 3) -> str:
    """List directory contents up to a specified depth, skipping ignored directories.

    Args:
        dir_path: Relative path from repository root.
        max_depth: Maximum recursion depth.

    Returns:
        Structured string representation of the directory tree.
    """
    try:
        root = _resolve_safe_path(dir_path)
        if not root.is_dir():
            return f"Error: Directory not found: '{dir_path}'"

        tree_lines: list[str] = [f"Directory tree for '{dir_path}':"]

        def _walk(current: Path, depth: int, prefix: str) -> None:
            if depth > max_depth:
                return
            try:
                children = sorted(
                    current.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                return

            for child in children:
                if child.name in IGNORE_DIRS:
                    continue

                rel = child.relative_to(REPO_ROOT).as_posix()
                if child.is_dir():
                    tree_lines.append(f"{prefix}|-- {child.name}/ ({rel})")
                    _walk(child, depth + 1, prefix + "|   ")
                else:
                    size = child.stat().st_size
                    tree_lines.append(f"{prefix}|-- {child.name} ({size} B)")

        _walk(root, 1, "")
        return "\n".join(tree_lines)
    except Exception as err:
        return f"Error listing directory '{dir_path}': {err}"


def search_code(query: str, sub_dir: str = ".") -> str:
    """Search for a text string or symbol across repository code files.

    Args:
        query: Search term (case-insensitive).
        sub_dir: Relative subdirectory to search within.

    Returns:
        Matching file paths and line numbers with matching line content.
    """
    try:
        start_dir = _resolve_safe_path(sub_dir)
        if not start_dir.is_dir():
            return f"Error: Search path not found: '{sub_dir}'"

        matches: list[str] = []
        lowered_query = query.lower()

        for root, dirs, files in os.walk(start_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in SEARCH_FILE_EXTENSIONS:
                    continue

                full_path = Path(root) / fname
                try:
                    rel_path = full_path.relative_to(REPO_ROOT).as_posix()
                    lines = full_path.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()

                    for idx, line in enumerate(lines, 1):
                        if lowered_query in line.lower():
                            matches.append(f"{rel_path}:{idx}: {line.strip()}")
                            if len(matches) >= 50:
                                matches.append("... [Search capped at 50 matches]")
                                return "\n".join(matches)
                except Exception:
                    continue

        if not matches:
            return f"No matches found for query: '{query}'"
        return "\n".join(matches)
    except Exception as err:
        return f"Error searching code for '{query}': {err}"


def run_tests(test_dir: str = "tests", timeout_sec: int = 30) -> str:
    """Execute repository unit tests and return the actual test execution output.

    Args:
        test_dir: Subdirectory containing unit tests.
        timeout_sec: Maximum test execution time in seconds.

    Returns:
        Actual test execution results including pass/fail status and tracebacks.
    """
    try:
        target = _resolve_safe_path(test_dir)
        if not target.is_dir():
            return f"Error: Test directory not found: '{test_dir}'"

        cmd = [sys.executable, "-m", "unittest", "discover", "-s", test_dir, "-v"]
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

        status = "PASSED" if result.returncode == 0 else f"FAILED (exit code {result.returncode})"
        return (
            f"Test Suite Status: {status}\n"
            f"STDOUT:\n{result.stdout.strip() or '(empty)'}\n"
            f"STDERR:\n{result.stderr.strip() or '(empty)'}"
        )
    except subprocess.TimeoutExpired:
        return f"Error: Tests timed out after {timeout_sec} seconds."
    except Exception as err:
        return f"Error running tests in '{test_dir}': {err}"


from radulov.mcp import get_gemini_doc, search_gemini_docs

TOOL_DEFINITIONS = [
    read_file,
    list_directory,
    search_code,
    run_tests,
    search_gemini_docs,
    get_gemini_doc,
]

