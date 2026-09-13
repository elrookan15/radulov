"""Bounded Deep Research Engine for RADULOV.

Executes Google Search Grounded research over Gemini with a strict
120-second timeout to discover current production libraries, benchmarks,
and architectural patterns.
"""

from __future__ import annotations

import concurrent.futures
import sys
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


from radulov import DEFAULT_MODEL

RESEARCH_PROMPT_TEMPLATE = """You are the Lead Cyber-Architect conducting deep research for RADULOV.
Your goal is to investigate modern 2026 production-grade best practices, libraries, and architectural patterns for the following user request within the context of this specific repository.

USER GOAL:
{user_goal}

REPOSITORY TOPOLOGY & ACTIVE STACK:
{codebase_summary}

RESEARCH REQUIREMENTS:
1. Identify the top 2026 industry-standard libraries, frameworks, or native APIs best suited for this task.
2. Analyze real-world performance benchmarks, bundle size impacts, and latency trade-offs.
3. Identify critical security pitfalls (OWASP Top 10, input validation, access control, memory/CPU hazards).
4. Provide technical evidence for two contrasting implementation philosophies:
   - Philosophy A: Minimalist, native, zero-dependency, ultra-lightweight.
   - Philosophy B: Feature-rich, highly extensible, modern production ecosystem suite.

Be dense, hyper-technical, objective, and empirical. Ground findings in current engineering reality.
"""


def _invoke_research(
    client: genai.Client,
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Invoke Gemini with Search Grounding or thinking fallback."""
    # Attempt 1: Search Grounded Generation
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=16384),
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception as search_err:
        sys.stderr.write(f"NOTICE: Search grounding fallback ({search_err}). Using high-reasoning mode.\n")

    # Attempt 2: High-Reasoning Fallback
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=32768),
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception as fallback_err:
        return f"Error conducting research: {fallback_err}"

    return "No research content generated."


def conduct_deep_research(
    client: genai.Client,
    user_goal: str,
    codebase_summary: str,
    timeout_sec: float = 120.0,
    model: str = DEFAULT_MODEL,
) -> str:
    """Conduct deep research with a strict time cap (default 120s)."""
    prompt = RESEARCH_PROMPT_TEMPLATE.format(
        user_goal=user_goal,
        codebase_summary=codebase_summary,
    )

    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="radulov-research"
    )
    future = executor.submit(_invoke_research, client, prompt, model)
    try:
        return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        sys.stderr.write(
            f"WARNING: Deep research timed out after {timeout_sec}s. "
            "Proceeding with local synthesis.\n"
        )
        return (
            f"Research timed out after {timeout_sec:.0f}s; relying on local "
            "repository topology and baseline Aegis invariants."
        )
    except Exception as err:
        return f"Research error: {err}"
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
