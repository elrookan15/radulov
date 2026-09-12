#!/usr/bin/env python3
"""RADULOV — GenAI Interaction Client.

Initializes the GenAI client with the Aegis system prompt and runs streaming
interactions against Gemini models.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
    from google.genai.errors import APIError
except ImportError:
    genai = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment, misc]

PROMPT_FILE = Path(__file__).parent / "prompts" / "aegis_system_prompt.md"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "models/gemini-3.7-flash")
DEFAULT_THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "medium")
DEFAULT_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))


def load_system_instruction(prompt_path: Path) -> str:
    """Load system prompt from markdown file."""
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"System prompt file not found at: {prompt_path.resolve()}"
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="RADULOV — Gemini Interaction Runner with Aegis Architecture"
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="user_input",
        help="Input query/task for the model. If omitted, prompts interactively.",
    )
    parser.add_argument(
        "--thinking-level",
        choices=["low", "medium", "high"],
        default=DEFAULT_THINKING_LEVEL,
        help=f"Thinking budget level (default: {DEFAULT_THINKING_LEVEL})",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max output tokens (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stream tokens to stdout in real time (default: --stream)",
    )
    return parser.parse_args()


def execute_interaction(
    client: genai.Client,
    model: str,
    user_input: str,
    system_instruction: str,
    generation_config: dict[str, object],
    stream: bool = True,
) -> None:
    """Execute the interaction, handling both streaming and synchronous modes."""
    if stream:
        for event in client.interactions.create(
            model=model,
            input=user_input,
            system_instruction=system_instruction,
            generation_config=generation_config,
            stream=True,
        ):
            if getattr(event, "event_type", None) == "step.delta":
                delta = getattr(event, "delta", None)
                if getattr(delta, "type", None) == "text":
                    print(delta.text, end="", flush=True)
            elif getattr(event, "event_type", None) == "interaction.completed":
                print()
    else:
        interaction = client.interactions.create(
            model=model,
            input=user_input,
            system_instruction=system_instruction,
            generation_config=generation_config,
            stream=False,
        )
        print(interaction.output_text)


def main() -> int:
    """Main execution entrypoint."""
    args = parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.stderr.write(
            "ERROR: GEMINI_API_KEY environment variable is not set.\n"
            "Set it in your environment or add it to a local .env file.\n"
            "Get a key from: https://aistudio.google.com/\n"
        )
        return 1

    if genai is None:
        sys.stderr.write(
            "ERROR: Required package 'google-genai' is not installed.\n"
            "Install dependencies with: pip install -r requirements.txt\n"
        )
        return 1

    user_input = args.user_input
    if not user_input:
        if not sys.stdin.isatty():
            user_input = sys.stdin.read().strip()
        else:
            try:
                user_input = input("Enter prompt for RADULOV: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                return 0

    if not user_input:
        sys.stderr.write("ERROR: Input prompt cannot be empty.\n")
        return 1

    try:
        system_instruction = load_system_instruction(PROMPT_FILE)
    except FileNotFoundError as err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 1

    client = genai.Client(api_key=api_key)

    generation_config = {
        "max_output_tokens": args.max_tokens,
        "thinking_level": args.thinking_level,
    }

    try:
        execute_interaction(
            client=client,
            model=args.model,
            user_input=user_input,
            system_instruction=system_instruction,
            generation_config=generation_config,
            stream=args.stream,
        )
        return 0
    except APIError as err:
        sys.stderr.write(f"API Error from Gemini service: {err}\n")
        return 2
    except Exception as err:
        sys.stderr.write(f"Unexpected error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
