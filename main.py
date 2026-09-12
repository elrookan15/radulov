#!/usr/bin/env python3
"""RADULOV — Autonomous Engineering Intelligence & GenAI Client.

Initializes the GenAI client with the Aegis system architecture, supporting
real-time streaming, multi-turn stateful REPL conversations, and repository
file context injection.
"""

from __future__ import annotations

import argparse
import datetime
import json
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
SESSIONS_DIR = Path(__file__).parent / ".radulov" / "sessions"

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "models/gemini-3.7-flash")
DEFAULT_THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "medium")
DEFAULT_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB per file


def load_system_instruction(prompt_path: Path) -> str:
    """Load system prompt from markdown file."""
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"System prompt file not found at: {prompt_path.resolve()}"
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def format_file_context(file_paths: list[str | Path]) -> str:
    """Read and format multiple repository files into a contextual prompt block."""
    context_blocks: list[str] = []

    for raw_path in file_paths:
        path = Path(raw_path)
        if not path.is_file():
            sys.stderr.write(f"WARNING: File not found, skipping: {raw_path}\n")
            continue

        try:
            size = path.stat().st_size
            if size > MAX_FILE_SIZE_BYTES:
                sys.stderr.write(
                    f"WARNING: File exceeds {MAX_FILE_SIZE_BYTES // 1024} KB limit, "
                    f"skipping: {path.name}\n"
                )
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            context_blocks.append(
                f"--- BEGIN FILE: {path.as_posix()} ---\n{content}\n--- END FILE: {path.as_posix()} ---"
            )
        except Exception as err:
            sys.stderr.write(f"WARNING: Could not read {raw_path}: {err}\n")

    return "\n\n".join(context_blocks)


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
        help="Input query/task for the model. If omitted in a TTY, launches interactive REPL.",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="files",
        action="append",
        default=[],
        help="Attach local file context to the prompt (can be specified multiple times).",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Force multi-turn interactive chat REPL mode.",
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
    previous_interaction_id: str | None = None,
) -> tuple[str, str | None]:
    """Execute the interaction, handling both streaming and synchronous modes.

    Returns a tuple of (full_output_text, new_interaction_id).
    """
    kwargs: dict[str, object] = {
        "model": model,
        "input": user_input,
        "system_instruction": system_instruction,
        "generation_config": generation_config,
    }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    output_chunks: list[str] = []
    interaction_id: str | None = None

    if stream:
        kwargs["stream"] = True
        events = client.interactions.create(**kwargs)
        for event in events:
            event_type = getattr(event, "event_type", None)
            if event_type == "step.delta":
                delta = getattr(event, "delta", None)
                if getattr(delta, "type", None) == "text":
                    text = getattr(delta, "text", "")
                    output_chunks.append(text)
                    print(text, end="", flush=True)
            elif event_type == "interaction.completed":
                interaction_obj = getattr(event, "interaction", None)
                if interaction_obj and hasattr(interaction_obj, "id"):
                    interaction_id = interaction_obj.id
                print()
    else:
        kwargs["stream"] = False
        interaction = client.interactions.create(**kwargs)
        text = getattr(interaction, "output_text", "")
        output_chunks.append(text)
        print(text)
        interaction_id = getattr(interaction, "id", None)

    return "".join(output_chunks), interaction_id


def save_session_turn(
    session_file: Path,
    turn: int,
    user_input: str,
    model_output: str,
    interaction_id: str | None,
) -> None:
    """Append a turn record to the session JSONL transcript."""
    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "turn": turn,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "interaction_id": interaction_id,
            "user_input": user_input,
            "model_output": model_output,
        }
        with session_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as err:
        sys.stderr.write(f"WARNING: Failed to log session transcript: {err}\n")


def run_chat_loop(
    client: genai.Client,
    model: str,
    system_instruction: str,
    generation_config: dict[str, object],
    initial_files: list[str],
    stream: bool = True,
) -> int:
    """Run an interactive multi-turn REPL loop maintaining server-side state."""
    session_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    session_file = SESSIONS_DIR / f"session_{session_timestamp}.jsonl"

    print("=" * 60)
    print(f"RADULOV Interactive Console — Aegis Architecture ({model})")
    print("Commands: /file <path> (attach file), /clear (reset session), /exit (quit)")
    print("=" * 60)

    previous_interaction_id: str | None = None
    attached_files: list[str] = list(initial_files)
    turn = 0

    if attached_files:
        print(f"Attached context files: {', '.join(attached_files)}")

    while True:
        try:
            user_input = input("\nradulov> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            print("Session ended.")
            break

        if user_input in ("/clear", "/reset"):
            previous_interaction_id = None
            attached_files.clear()
            print("Conversation state reset. Started fresh session context.")
            continue

        if user_input.startswith("/file "):
            file_arg = user_input[6:].strip()
            if Path(file_arg).is_file():
                attached_files.append(file_arg)
                print(f"Attached file: {file_arg}")
            else:
                print(f"Error: File not found: {file_arg}")
            continue

        if user_input == "/history":
            print(f"Total turns: {turn} | Current Interaction ID: {previous_interaction_id or 'None'}")
            print(f"Attached files: {', '.join(attached_files) if attached_files else 'None'}")
            continue

        # Prepare payload with any attached file context
        payload = user_input
        if attached_files:
            file_context = format_file_context(attached_files)
            if file_context:
                payload = f"Context files:\n{file_context}\n\nUser request:\n{user_input}"
            # File context sent for this turn; retain in history via interaction state
            attached_files.clear()

        turn += 1
        try:
            output_text, new_id = execute_interaction(
                client=client,
                model=model,
                user_input=payload,
                system_instruction=system_instruction,
                generation_config=generation_config,
                stream=stream,
                previous_interaction_id=previous_interaction_id,
            )
            if new_id:
                previous_interaction_id = new_id

            save_session_turn(session_file, turn, user_input, output_text, new_id)
        except APIError as err:
            sys.stderr.write(f"\nAPI Error from Gemini service: {err}\n")
        except Exception as err:
            sys.stderr.write(f"\nUnexpected error: {err}\n")

    return 0


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

    try:
        system_instruction = load_system_instruction(PROMPT_FILE)
    except FileNotFoundError as err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 1

    client = genai.Client(api_key=api_key)

    generation_config: dict[str, object] = {
        "max_output_tokens": args.max_tokens,
        "thinking_level": args.thinking_level,
    }

    # If --chat requested or no input passed and running interactively in terminal
    is_interactive_terminal = sys.stdin.isatty() and not args.user_input
    if args.chat or is_interactive_terminal:
        return run_chat_loop(
            client=client,
            model=args.model,
            system_instruction=system_instruction,
            generation_config=generation_config,
            initial_files=args.files,
            stream=args.stream,
        )

    # Single-shot execution mode
    user_input = args.user_input
    if not user_input:
        if not sys.stdin.isatty():
            user_input = sys.stdin.read().strip()

    if not user_input:
        sys.stderr.write("ERROR: Input prompt cannot be empty.\n")
        return 1

    # Attach file context if provided via -f/--file
    if args.files:
        file_context = format_file_context(args.files)
        if file_context:
            user_input = f"Context files:\n{file_context}\n\nUser request:\n{user_input}"

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
