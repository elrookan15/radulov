#!/usr/bin/env python3
"""RADULOV — Autonomous Engineering Intelligence & GenAI Client.

Initializes the GenAI client with the Aegis system architecture, supporting
real-time streaming, multi-turn stateful REPL conversations, repository
file context injection, grounded read-only engineering tools, and the
5-phase Autonomous Deep Research & Construction Pipeline.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

from radulov import DEFAULT_MODEL as PACKAGE_DEFAULT_MODEL
from radulov.builder import execute_autonomous_build
from radulov.researcher import conduct_deep_research
from radulov.scanner import format_scan_summary, scan_repository
from radulov.skills import compose_system_instruction
from radulov.synthesizer import format_options_card, synthesize_dual_options
from radulov.tools import (
    FUNCTION_DECLARATIONS,
    REPO_ROOT,
    _resolve_safe_path,
    collect_function_calls,
    dispatch_tool,
    format_function_result,
    get_gemini_doc,
    list_directory,
    list_skills,
    read_file,
    read_skill,
    run_tests,
    search_code,
    search_gemini_docs,
)

PROMPT_FILE = Path(__file__).parent / "prompts" / "aegis_system_prompt.md"
SESSIONS_DIR = Path(__file__).parent / ".radulov" / "sessions"

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", PACKAGE_DEFAULT_MODEL)
DEFAULT_THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "medium")
DEFAULT_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB per file
MAX_TOOL_ROUNDS = 8


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
        try:
            path = _resolve_safe_path(raw_path)
        except PermissionError as err:
            sys.stderr.write(f"WARNING: {err}\n")
            continue

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
            try:
                display = path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                display = path.as_posix()
            context_blocks.append(
                f"--- BEGIN FILE: {display} ---\n{content}\n--- END FILE: {display} ---"
            )
        except Exception as err:
            sys.stderr.write(f"WARNING: Could not read {raw_path}: {err}\n")

    return "\n\n".join(context_blocks)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="RADULOV — Autonomous Engineering Intelligence (Aegis Architecture)"
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
        "-b",
        "--build",
        dest="build_goal",
        metavar="GOAL",
        help="Trigger 5-Phase Autonomous Deep Research, Dual-Option Synthesis & Construction.",
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
        "--tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Equip Aegis with local read-only repository inspection tools (default: --tools).",
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

    # Local CLI shortcuts
    parser.add_argument(
        "--run-tests",
        dest="cli_run_tests",
        action="store_true",
        help="Directly run local unit tests and exit.",
    )
    parser.add_argument(
        "--grep",
        dest="cli_grep",
        metavar="QUERY",
        help="Directly search codebase for a string and exit.",
    )
    parser.add_argument(
        "--tree",
        dest="cli_tree",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Directly display the repository directory tree and exit.",
    )
    parser.add_argument(
        "--docs",
        "--gemini-docs",
        dest="cli_gemini_docs",
        metavar="QUERY",
        help="Search official Google Gemini API and SDK documentation (MCP) and exit.",
    )
    parser.add_argument(
        "--skills",
        "--list-skills",
        dest="cli_list_skills",
        action="store_true",
        help="List all discovered agent skills and exit.",
    )
    parser.add_argument(
        "--skill",
        dest="cli_read_skill",
        metavar="NAME",
        help="Display instructions for a specific agent skill (e.g. 'gemini-api-dev') and exit.",
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
    enable_tools: bool = True,
) -> tuple[str, str | None]:
    """Execute the interaction, including client-side function-call rounds."""
    current_input: Any = user_input
    current_previous_id = previous_interaction_id
    last_text = ""
    interaction_id: str | None = None
    tool_decls = FUNCTION_DECLARATIONS if enable_tools else None

    for _round in range(MAX_TOOL_ROUNDS + 1):
        kwargs: dict[str, object] = {
            "model": model,
            "input": current_input,
            "system_instruction": system_instruction,
            "generation_config": generation_config,
        }
        if current_previous_id:
            kwargs["previous_interaction_id"] = current_previous_id
        if tool_decls is not None:
            kwargs["tools"] = tool_decls

        interaction: Any = None
        round_chunks: list[str] = []
        streamed_steps: list[Any] = []

        if stream:
            kwargs["stream"] = True
            events = client.interactions.create(**kwargs)
            for event in events:
                event_type = getattr(event, "event_type", None)
                if event_type == "step.delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) == "text":
                        text = getattr(delta, "text", "")
                        round_chunks.append(text)
                        print(text, end="", flush=True)
                elif event_type == "step.start":
                    step = getattr(event, "step", None)
                    if step is not None:
                        streamed_steps.append(step)
                elif event_type == "interaction.completed":
                    interaction = getattr(event, "interaction", None)
                    if interaction and hasattr(interaction, "id"):
                        interaction_id = interaction.id
                    print()
        else:
            kwargs["stream"] = False
            interaction = client.interactions.create(**kwargs)
            text = getattr(interaction, "output_text", "") or ""
            if text:
                print(text)
            round_chunks.append(text)
            interaction_id = getattr(interaction, "id", None)

        last_text = "".join(round_chunks)
        calls = collect_function_calls(interaction)
        if not calls and streamed_steps:
            calls = collect_function_calls(SimpleNamespace(steps=streamed_steps))
        if not calls:
            return last_text, interaction_id

        results = []
        for call in calls:
            result_text = dispatch_tool(call["name"], call["arguments"])
            sys.stderr.write(f"[tool] {call['name']}\n")
            results.append(format_function_result(call, result_text))

        current_input = results
        current_previous_id = interaction_id

    sys.stderr.write(
        f"WARNING: Tool loop stopped after {MAX_TOOL_ROUNDS} rounds.\n"
    )
    return last_text, interaction_id


def run_autonomous_pipeline(
    client: genai.Client,
    user_goal: str,
    model: str = DEFAULT_MODEL,
    repo_root: Path = Path("."),
) -> int:
    """Execute the 5-Phase Deep Research, Dual-Option Synthesis & Construction Workflow."""
    print("=" * 70)
    print(f"RADULOV AUTONOMOUS SYNTHESIS & CONSTRUCTION ENGINE")
    print(f"Goal: {user_goal}")
    print("=" * 70)

    # Stage 1: Ingest & Topology Extraction
    print("\n[1/4] Scanning repository topology and dependencies...")
    scan_data = scan_repository(repo_root)
    codebase_summary = format_scan_summary(scan_data)
    languages = ", ".join(scan_data["detected_languages"]) or "Generic"
    print(f"  + Ingested {scan_data['total_files']} files (Detected: {languages}).")

    # Stage 2: Bounded Live Research
    print("\n[2/4] Conducting bounded deep ecosystem research & benchmarks (max 120s)...")
    research_report = conduct_deep_research(
        client=client,
        user_goal=user_goal,
        codebase_summary=codebase_summary,
        timeout_sec=120.0,
        model=model,
    )
    print("  + Deep research synthesis completed.")

    # Stage 3: Dual-Option Synthesis
    print("\n[3/4] Synthesizing Dual-Option Architecture Plans...")
    try:
        options = synthesize_dual_options(
            client=client,
            user_goal=user_goal,
            codebase_summary=codebase_summary,
            research_report=research_report,
            model=model,
        )
        print(format_options_card(options))
    except Exception as err:
        sys.stderr.write(f"ERROR: Option synthesis failed: {err}\n")
        return 1

    # Stage 4: User Selection Gate
    chosen_option: dict[str, Any] | None = None
    while True:
        try:
            choice = input("Select option [1 for Option A, 2 for Option B, q to quit]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return 0

        if choice in ("q", "quit", "exit"):
            print("Construction aborted by user.")
            return 0
        if choice in ("1", "a", "option 1", "option a"):
            chosen_option = options.get("option_a")
            break
        if choice in ("2", "b", "option 2", "option b"):
            chosen_option = options.get("option_b")
            break
        print("Invalid choice. Please enter 1, 2, or q.")

    if not chosen_option:
        sys.stderr.write("ERROR: No valid option selected.\n")
        return 1

    # Stage 5: Autonomous Construction & Verification
    print(f"\n[4/4] Executing Autonomous Construction & Verification for: {chosen_option.get('title', 'Selected Plan')}")
    build_result = execute_autonomous_build(
        client=client,
        chosen_option=chosen_option,
        user_goal=user_goal,
        codebase_summary=codebase_summary,
        repo_root=repo_root,
        model=model,
    )

    print("\n" + "=" * 70)
    print(f"BUILD STATUS: {build_result.get('status')}")
    print(f"Generated Files: {len(build_result.get('written_files', []))}")
    if build_result.get("repair_attempts", 0) > 0:
        print(f"Self-Correction Loops: {build_result.get('repair_attempts')}")
    print("=" * 70)

    return 0 if build_result.get("status") == "SUCCESS" else 1


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


def _new_session_file() -> Path:
    """Create a timestamped session transcript path under SESSIONS_DIR."""
    session_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    return SESSIONS_DIR / f"session_{session_timestamp}.jsonl"


def print_chat_help(model: str | None = None) -> None:
    """Print the interactive REPL command banner."""
    print("=" * 65)
    if model:
        print(f"RADULOV Interactive Console — Aegis Architecture ({model})")
    else:
        print("RADULOV Interactive Console — Commands")
    print("Commands:")
    print("  /help          — Show this command list")
    print("  /build <goal>  — Run Deep Research & Construction Pipeline")
    print("  /skills        — List all discovered agent skills")
    print("  /skill <name>  — View instructions for a specific skill")
    print("  /docs <query>  — Search official Gemini API & SDK docs (MCP)")
    print("  /doc <chunk_id>— Retrieve Gemini doc chunk (MCP)")
    print("  /file <path>   — Attach file to context")
    print("  /read <path>   — Inspect file locally")
    print("  /grep <term>   — Search repository code")
    print("  /ls [path]     — List directory tree")
    print("  /test [dir]    — Run unit test suite")
    print("  /clear         — Reset conversational state (new session file)")
    print("  /history       — View session metrics")
    print("  /exit          — Quit console")
    print("=" * 65)


def _split_slash_command(user_input: str) -> tuple[str, str] | None:
    """Return (command, argument) for slash inputs, else None."""
    if not user_input.startswith("/"):
        return None
    if " " in user_input:
        command, argument = user_input.split(" ", 1)
        return command.lower(), argument.strip()
    return user_input.lower(), ""


def handle_chat_command(
    user_input: str,
    *,
    client: genai.Client,
    model: str,
    attached_files: list[str],
    session: dict[str, Any],
) -> bool:
    """Handle a slash command. Return True when the input was consumed."""
    parsed = _split_slash_command(user_input)
    if parsed is None:
        return False

    command, argument = parsed

    if command in ("/exit", "/quit"):
        session["should_exit"] = True
        print("Session ended.")
        return True

    if command in ("/help", "/?"):
        print_chat_help()
        return True

    if command in ("/clear", "/reset"):
        session["previous_interaction_id"] = None
        session["turn"] = 0
        session["session_file"] = _new_session_file()
        attached_files.clear()
        print(
            "Conversation state reset. New session transcript: "
            f"{session['session_file']}"
        )
        return True

    if command == "/build":
        if not argument:
            print("Usage: /build <feature or goal description>")
            return True
        run_autonomous_pipeline(client, argument, model=model)
        return True

    if command in ("/skills", "/list-skills"):
        print(list_skills())
        return True

    if command == "/skill":
        if not argument:
            print("Usage: /skill <name>")
            return True
        print(read_skill(argument))
        return True

    if command in ("/docs", "/gemini-docs"):
        if not argument:
            print("Usage: /docs <query>")
            return True
        print(search_gemini_docs(argument))
        return True

    if command in ("/doc", "/gemini-doc"):
        if not argument:
            print("Usage: /doc <chunk_id>")
            return True
        print(get_gemini_doc(argument))
        return True

    if command == "/read":
        if not argument:
            print("Usage: /read <path>")
            return True
        print(read_file(argument))
        return True

    if command == "/grep":
        if not argument:
            print("Usage: /grep <term>")
            return True
        print(search_code(argument))
        return True

    if command == "/ls":
        print(list_directory(argument or "."))
        return True

    if command == "/test":
        print(run_tests(argument or "tests"))
        return True

    if command == "/file":
        if not argument:
            print("Usage: /file <path>")
            return True
        try:
            resolved = _resolve_safe_path(argument)
        except PermissionError as err:
            print(f"Error: {err}")
            return True
        if resolved.is_file():
            attached_files.append(argument)
            print(f"Attached file: {argument}")
        else:
            print(f"Error: File not found: {argument}")
        return True

    if command == "/history":
        print(
            f"Total turns: {session['turn']} | "
            f"Current Interaction ID: {session['previous_interaction_id'] or 'None'}"
        )
        print(
            f"Attached files: "
            f"{', '.join(attached_files) if attached_files else 'None'}"
        )
        print(f"Session transcript: {session['session_file']}")
        return True

    # Unknown slash command — keep it in the REPL, do not send to the model.
    print(f"Unknown command: {command}. Type /help for available commands.")
    return True


def run_chat_loop(
    client: genai.Client,
    model: str,
    system_instruction: str,
    generation_config: dict[str, object],
    initial_files: list[str],
    stream: bool = True,
    enable_tools: bool = True,
) -> int:
    """Run an interactive multi-turn REPL loop maintaining server-side state."""
    session: dict[str, Any] = {
        "previous_interaction_id": None,
        "turn": 0,
        "session_file": _new_session_file(),
        "should_exit": False,
    }
    attached_files: list[str] = list(initial_files)

    print_chat_help(model)

    if attached_files:
        print(f"Attached context files: {', '.join(attached_files)}")

    while not session["should_exit"]:
        try:
            user_input = input("\nradulov> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if handle_chat_command(
            user_input,
            client=client,
            model=model,
            attached_files=attached_files,
            session=session,
        ):
            continue

        # Prepare payload with any attached file context.
        # Only drop attachments that successfully loaded into context.
        payload = user_input
        if attached_files:
            loaded_paths: list[str] = []
            context_blocks: list[str] = []
            for path in list(attached_files):
                block = format_file_context([path])
                if block:
                    loaded_paths.append(path)
                    context_blocks.append(block)
            for path in loaded_paths:
                attached_files.remove(path)
            if context_blocks:
                file_context = "\n\n".join(context_blocks)
                payload = (
                    f"Context files:\n{file_context}\n\nUser request:\n{user_input}"
                )
            elif attached_files:
                print(
                    "WARNING: Attached files could not be loaded; "
                    "sending prompt without file context."
                )

        try:
            output_text, new_id = execute_interaction(
                client=client,
                model=model,
                user_input=payload,
                system_instruction=system_instruction,
                generation_config=generation_config,
                stream=stream,
                previous_interaction_id=session["previous_interaction_id"],
                enable_tools=enable_tools,
            )
        except KeyboardInterrupt:
            print("\nGeneration interrupted. Conversation state preserved.")
            continue
        except APIError as err:
            sys.stderr.write(f"\nAPI Error from Gemini service: {err}\n")
            continue
        except Exception as err:
            sys.stderr.write(f"\nUnexpected error: {err}\n")
            continue

        session["turn"] += 1
        if new_id:
            session["previous_interaction_id"] = new_id
        save_session_turn(
            session["session_file"],
            session["turn"],
            user_input,
            output_text,
            new_id,
        )

    return 0


def main() -> int:
    """Main execution entrypoint."""
    args = parse_args()

    # Handle direct CLI tool shortcuts without requiring API key
    if args.cli_run_tests:
        print(run_tests("tests"))
        return 0

    if args.cli_grep:
        print(search_code(args.cli_grep))
        return 0

    if args.cli_tree is not None:
        print(list_directory(args.cli_tree))
        return 0

    if args.cli_gemini_docs:
        print(search_gemini_docs(args.cli_gemini_docs))
        return 0

    if args.cli_list_skills:
        print(list_skills())
        return 0

    if args.cli_read_skill:
        print(read_skill(args.cli_read_skill))
        return 0

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

    client = genai.Client(api_key=api_key)

    # If --build requested: run the 5-phase Deep Research & Construction Pipeline
    if args.build_goal:
        return run_autonomous_pipeline(
            client=client,
            user_goal=args.build_goal,
            model=args.model,
        )

    try:
        system_instruction = compose_system_instruction(
            load_system_instruction(PROMPT_FILE)
        )
    except FileNotFoundError as err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 1

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
            enable_tools=args.tools,
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
            enable_tools=args.tools,
        )
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\nGeneration interrupted.\n")
        return 130
    except APIError as err:
        sys.stderr.write(f"API Error from Gemini service: {err}\n")
        return 2
    except Exception as err:
        sys.stderr.write(f"Unexpected error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
