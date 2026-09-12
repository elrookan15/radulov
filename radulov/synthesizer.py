"""Dual-Option Architecture Synthesizer for RADULOV.

Transforms research findings and repository topology into two contrasting,
production-grade architectural options for user selection.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


SYNTHESIS_PROMPT = """You are the Lead Systems Architect for RADULOV.
Based on the user's goal, the repository topology, and the deep research report, synthesize EXACTLY TWO contrasting, optimized architectural options for implementation.

USER GOAL:
{user_goal}

REPOSITORY TOPOLOGY:
{codebase_summary}

DEEP RESEARCH REPORT:
{research_report}

OUTPUT SCHEMA REQUIREMENTS:
You must respond with ONLY a valid JSON object matching this schema (no markdown fences, no preamble):
{{
  "user_intent_summary": "<concise summary of what the user is trying to accomplish>",
  "option_a": {{
    "title": "<Name of Option A (e.g. Option A: Streamlined Native Implementation)>",
    "philosophy": "<e.g. Minimal dependencies, highest raw execution speed, zero supply-chain overhead>",
    "tech_stack": ["<list of libraries/native APIs>"],
    "files_to_create_or_modify": ["<list of exact relative file paths>"],
    "architecture_summary": "<dense 2-3 sentence technical description of the architecture>",
    "pros": ["<3-4 key bullet points>"],
    "cons": ["<2-3 key trade-offs>"],
    "estimated_bundle_or_memory_delta": "<e.g. 0 KB external deps, ~2ms latency>"
  }},
  "option_b": {{
    "title": "<Name of Option B (e.g. Option B: Advanced State-of-the-Art Suite)>",
    "philosophy": "<e.g. Maximum feature richness, full reactivity, modular extensibility>",
    "tech_stack": ["<list of libraries/tools>"],
    "files_to_create_or_modify": ["<list of exact relative file paths>"],
    "architecture_summary": "<dense 2-3 sentence technical description of the architecture>",
    "pros": ["<3-4 key bullet points>"],
    "cons": ["<2-3 key trade-offs>"],
    "estimated_bundle_or_memory_delta": "<e.g. +14 KB deps, rich animations/features>"
  }}
}}
"""


def _extract_json(raw_text: str) -> dict[str, Any]:
    """Extract and parse JSON from model output."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: search for first { and last }
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Could not parse valid JSON from model response:\n{raw_text[:500]}")


def synthesize_dual_options(
    client: genai.Client,
    user_goal: str,
    codebase_summary: str,
    research_report: str,
    model: str = "models/gemini-3.7-flash",
) -> dict[str, Any]:
    """Synthesize two optimized architectural options using Gemini."""
    prompt = SYNTHESIS_PROMPT.format(
        user_goal=user_goal,
        codebase_summary=codebase_summary,
        research_report=research_report,
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=8192),
        ),
    )

    if not response or not response.text:
        raise RuntimeError("Empty response from Gemini during option synthesis.")

    return _extract_json(response.text)


def format_options_card(options_data: dict[str, Any]) -> str:
    """Format the dual options into a clean, human-readable terminal display."""
    intent = options_data.get("user_intent_summary", "Feature Request")
    opt_a = options_data.get("option_a", {})
    opt_b = options_data.get("option_b", {})

    def _render_option(opt: dict[str, Any], key_num: int) -> str:
        title = opt.get("title", f"Option {key_num}")
        philosophy = opt.get("philosophy", "")
        tech = ", ".join(opt.get("tech_stack", [])) or "Native"
        files = ", ".join(opt.get("files_to_create_or_modify", [])) or "N/A"
        summary = opt.get("architecture_summary", "")
        pros = "\n".join(f"      + {p}" for p in opt.get("pros", []))
        cons = "\n".join(f"      - {c}" for c in opt.get("cons", []))
        perf = opt.get("estimated_bundle_or_memory_delta", "N/A")

        return (
            f"  [{key_num}] {title.upper()}\n"
            f"      Philosophy:   {philosophy}\n"
            f"      Tech Stack:   {tech}\n"
            f"      Target Files: {files}\n"
            f"      Footprint:    {perf}\n"
            f"      Overview:     {summary}\n"
            f"      Advantages:\n{pros}\n"
            f"      Trade-offs:\n{cons}\n"
        )

    return (
        f"\n{'=' * 70}\n"
        f"RADULOV ARCHITECTURAL SYNTHESIS (Grounded in Deep Research)\n"
        f"Goal: {intent}\n"
        f"{'=' * 70}\n\n"
        f"{_render_option(opt_a, 1)}\n"
        f"{'-' * 70}\n\n"
        f"{_render_option(opt_b, 2)}\n"
        f"{'=' * 70}\n"
    )
