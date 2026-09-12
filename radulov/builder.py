"""Autonomous Construction & Self-Correction Engine for RADULOV.

Generates complete, production-grade files (zero placeholders) based on the
chosen architectural option, writes unit tests, and verifies execution via
the Aegis Red-Green-Verify self-correction loop.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


from radulov.tools import run_tests

BUILDER_PROMPT = """You are Aegis, the Lead Cyber-Architect executing construction for RADULOV.
Implement the chosen architectural option with 100% completeness. No placeholders, no TODOs, no pseudo-code.
Every file must be fully functional, type-safe, and production-ready.

CHOSEN ARCHITECTURAL OPTION:
{chosen_option_json}

USER GOAL:
{user_goal}

REPOSITORY TOPOLOGY:
{codebase_summary}

CONSTRUCTION MANDATES:
1. Generate all source code files listed in the option.
2. Generate comprehensive automated unit tests for all new functionality.
3. Apply defensive programming (input validation, error handling, least privilege).
4. Output MUST be a single valid JSON object with the following schema (no markdown formatting outside JSON):
{{
  "files": [
    {{
      "path": "<relative file path from repo root>",
      "content": "<exact full file content string>",
      "description": "<brief rationale>"
    }}
  ],
  "build_notes": "<summary of what was built and security measures applied>"
}}
"""

REPAIR_PROMPT = """The unit tests failed after applying the patch. Self-correct the implementation according to the Aegis Red-Green-Verify protocol.

TEST FAILURE TRACEBACK:
{test_output}

PREVIOUS IMPLEMENTATION:
{previous_files_json}

Diagnose the root cause, fix the defect, and return the corrected files in the exact same JSON schema:
{{
  "files": [
    {{
      "path": "<relative file path>",
      "content": "<corrected full file content>",
      "description": "<fix explanation>"
    }}
  ],
  "build_notes": "<summary of bug fix>"
}}
"""


def _extract_builder_json(raw_text: str) -> dict[str, Any]:
    """Extract and parse JSON from model output."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Could not parse valid JSON from builder output:\n{raw_text[:500]}")


def _write_files_to_disk(files_list: list[dict[str, str]], repo_root: Path) -> list[str]:
    """Write generated files to disk safely."""
    written: list[str] = []
    for item in files_list:
        rel_path = item.get("path", "").strip()
        content = item.get("content", "")
        if not rel_path or not content:
            continue

        target_file = (repo_root / rel_path).resolve()
        # Security check: ensure path is within repo
        target_file.relative_to(repo_root)

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        written.append(rel_path)

    return written


def execute_autonomous_build(
    client: genai.Client,
    chosen_option: dict[str, Any],
    user_goal: str,
    codebase_summary: str,
    repo_root: Path = Path("."),
    max_repair_attempts: int = 2,
    model: str = "models/gemini-3.7-flash",
) -> dict[str, Any]:
    """Generate complete files, write to disk, run tests, and self-correct if needed."""
    root = repo_root.resolve()

    print("\n[Aegis Builder] Synthesizing full-stack production code and unit tests...")
    prompt = BUILDER_PROMPT.format(
        chosen_option_json=json.dumps(chosen_option, indent=2),
        user_goal=user_goal,
        codebase_summary=codebase_summary,
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=16384),
        ),
    )

    if not response or not response.text:
        return {"status": "FAILED", "error": "Empty model response during code construction."}

    build_data = _extract_builder_json(response.text)
    files_list = build_data.get("files", [])
    written_files = _write_files_to_disk(files_list, root)

    for f in written_files:
        print(f"  + Generated: {f}")

    # Run verification tests
    print("\n[Aegis Builder] Executing automated verification suite (Red-Green-Verify)...")
    test_results = run_tests("tests")
    print(test_results)

    # Self-correction loop if tests fail
    attempt = 0
    while "FAILED" in test_results and attempt < max_repair_attempts:
        attempt += 1
        print(f"\n[Aegis Builder] Test failure detected. Initiating Self-Correction Attempt {attempt}/{max_repair_attempts}...")

        repair_prompt = REPAIR_PROMPT.format(
            test_output=test_results,
            previous_files_json=json.dumps(files_list, indent=2),
        )

        repair_resp = client.models.generate_content(
            model=model,
            contents=repair_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=16384),
            ),
        )

        if repair_resp and repair_resp.text:
            try:
                repaired_data = _extract_builder_json(repair_resp.text)
                files_list = repaired_data.get("files", [])
                written_files = _write_files_to_disk(files_list, root)
                for f in written_files:
                    print(f"  * Repaired: {f}")

                test_results = run_tests("tests")
                print(test_results)
            except Exception as err:
                sys.stderr.write(f"Repair attempt {attempt} failed to parse: {err}\n")

    passed = "PASSED" in test_results
    return {
        "status": "SUCCESS" if passed else "COMPLETED_WITH_TEST_WARNINGS",
        "written_files": written_files,
        "test_results": test_results,
        "build_notes": build_data.get("build_notes", ""),
        "repair_attempts": attempt,
    }
