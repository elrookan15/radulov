"""Grounded Engineering Tools for RADULOV Aegis Intelligence.

Provides deterministic, read-only repository inspection and test runner tools
to ensure Aegis never hallucinates execution evidence or file contents.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

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


def _run_unittest(repo_root: Path, test_dir: str = "tests", timeout_sec: int = 30) -> str:
    """Run unittest discovery under an explicit repository root."""
    try:
        root = repo_root.resolve()
        target = (root / test_dir).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return f"Error: Access denied: '{test_dir}' is outside repository root."
        if not target.is_dir():
            return f"Error: Test directory not found: '{test_dir}'"

        cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(test_dir), "-v"]
        result = subprocess.run(
            cmd,
            cwd=str(root),
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


def run_tests(test_dir: str = "tests", timeout_sec: int = 30) -> str:
    """Execute repository unit tests and return the actual test execution output.

    Args:
        test_dir: Subdirectory containing unit tests.
        timeout_sec: Maximum test execution time in seconds.

    Returns:
        Actual test execution results including pass/fail status and tracebacks.
    """
    return _run_unittest(REPO_ROOT, test_dir=test_dir, timeout_sec=timeout_sec)


from radulov.mcp import get_gemini_doc, search_gemini_docs
from radulov.skills import list_skills, read_skill

TOOL_DEFINITIONS = [
    read_file,
    list_directory,
    search_code,
    run_tests,
    search_gemini_docs,
    get_gemini_doc,
    list_skills,
    read_skill,
]

TOOL_MAP: dict[str, Callable[..., Any]] = {
    func.__name__: func for func in TOOL_DEFINITIONS
}


def _json_schema_for_annotation(annotation: Any) -> dict[str, str]:
    """Map a Python annotation to a JSON Schema type for Interactions tools."""
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    arg_types = getattr(annotation, "__args__", None)
    names = [
        getattr(item, "__name__", str(item))
        for item in (arg_types or (annotation,))
        if item is not type(None)
    ]
    if names == ["int"]:
        return {"type": "integer"}
    if names == ["float"]:
        return {"type": "number"}
    if names == ["bool"]:
        return {"type": "boolean"}
    return {"type": "string"}


def function_to_declaration(func: Callable[..., Any]) -> dict[str, Any]:
    """Convert a Python callable into an Interactions API function declaration."""
    signature = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        properties[name] = _json_schema_for_annotation(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(name)

    description = inspect.getdoc(func) or func.__name__
    description = description.strip().split("\n", 1)[0]

    return {
        "type": "function",
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


FUNCTION_DECLARATIONS: list[dict[str, Any]] = [
    function_to_declaration(func) for func in TOOL_DEFINITIONS
]


def _coerce_arguments(raw: Any) -> dict[str, Any]:
    """Normalize model-provided tool arguments to a dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def collect_function_calls(interaction: Any) -> list[dict[str, Any]]:
    """Extract function_call steps from an Interaction. Non-list steps are ignored."""
    steps = getattr(interaction, "steps", None)
    if not isinstance(steps, (list, tuple)):
        return []

    calls: list[dict[str, Any]] = []
    for step in steps:
        if getattr(step, "type", None) != "function_call":
            continue
        calls.append(
            {
                "name": getattr(step, "name", "") or "",
                "call_id": getattr(step, "id", "") or "",
                "arguments": _coerce_arguments(getattr(step, "arguments", None)),
            }
        )
    return calls


def dispatch_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Execute a registered grounded tool and return its string result."""
    func = TOOL_MAP.get(name)
    if func is None:
        return f"Error: Unknown tool '{name}'."
    args = arguments if isinstance(arguments, dict) else {}
    try:
        result = func(**args)
    except TypeError as err:
        return f"Error calling '{name}': {err}"
    except Exception as err:
        return f"Error executing '{name}': {err}"
    return str(result)


def format_function_result(call: dict[str, Any], result_text: str) -> dict[str, Any]:
    """Build an Interactions function_result payload for a completed tool call."""
    return {
        "type": "function_result",
        "name": call.get("name", ""),
        "call_id": call.get("call_id", ""),
        "result": [{"type": "text", "text": result_text}],
    }


