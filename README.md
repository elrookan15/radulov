# RADULOV

[![CI](https://github.com/elrookan15/radulov/actions/workflows/ci.yml/badge.svg)](https://github.com/elrookan15/radulov/actions/workflows/ci.yml)

Autonomous engineering intelligence and Gemini client interface configured with the **Aegis** system architecture.

## Features

- **5-Phase Autonomous Synthesis & Construction (`--build / -b`)**:
  1. **Topology Scan**: Rapid AST and dependency manifest extraction.
  2. **Bounded Deep Research**: Google Search Grounded ecosystem investigation (strict 120s time cap).
  3. **Dual-Option Synthesis**: Generates Option A (Streamlined/Native) vs. Option B (Advanced/Scalable).
  4. **Human Selection Gate**: Interactive prompt awaiting your architectural approval.
  5. **Aegis Construction & Self-Correction**: Synthesizes 100% complete files, writes unit tests, and verifies execution via the Red-Green-Verify loop.
- **Aegis Architecture Governance**: Grounded by [prompts/aegis_system_prompt.md](prompts/aegis_system_prompt.md) and [AGENTS.md](AGENTS.md).
- **Grounded Engineering Tools (`--tools`)**: Declares local tools (`read_file`, `list_directory`, `search_code`, `run_tests`) to Gemini, executes `function_call` steps locally, and sends `function_result` back so Aegis cannot hallucinate file contents or test results.
- **Stateful Multi-Turn REPL (`--chat`)**: Interactive console remembering context turns via Gemini Interactions server-side state.
- **Repository File Context Injection (`-f / --file`)**: Attach local source files directly into model reasoning context.
- **CLI Development Shortcuts**: Direct developer tools for `--tree`, `--grep <query>`, and `--run-tests` without model invocation overhead.
- **Real-Time Streaming**: Incremental token delivery via `step.delta` events with `--no-stream` fallback.
- **Hyperparameter Controls**: Configurable thinking budget (`--thinking-level`), token limits (`--max-tokens`), and model targets (`--model`).
- **Session Audit Logging**: Transcripts automatically recorded to local `.radulov/sessions/` (ignored by Git).
- **Automated CI Matrix**: GitHub Actions verifying Python 3.10, 3.11, and 3.12 across all pushes and PRs.

## Repository Structure

```text
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI matrix (Python 3.10, 3.11, 3.12)
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules for Python, virtualenvs, sessions, and secrets
├── AGENTS.md                   # Apex agent directives and operational governance
├── README.md                   # Project documentation
├── pyproject.toml              # PEP 621 packaging & linter configuration (v0.3.0)
├── requirements.txt            # Python dependencies
├── main.py                     # Entrypoint CLI runner with streaming, REPL, and build pipeline
├── radulov/
│   ├── __init__.py             # Package declaration
│   ├── skills.py               # Skills discovery, parsing & prompt context engine
│   ├── mcp.py                  # Model Context Protocol (MCP) client & Gemini API docs integration
│   ├── tools.py                # Grounded engineering tools (read, search, tree, test runner, Gemini docs, skills)
│   ├── scanner.py              # Repository topology & manifest scanner
│   ├── researcher.py           # Bounded Google Search Grounded research engine (120s SLA)
│   ├── synthesizer.py          # Dual-option architectural plan synthesizer
│   └── builder.py              # Autonomous code construction & Red-Green-Verify self-correction
├── archive/
│   └── ai_studio_code.py       # Archived raw export from Google AI Studio
├── prompts/
│   └── aegis_system_prompt.md  # Core Aegis engineering intelligence system prompt
└── tests/
    ├── test_main.py            # CLI and runner unit tests (12 tests)
    ├── test_tools.py           # Grounded tools unit tests (13 tests)
    ├── test_mcp.py             # MCP client & Gemini docs unit tests (19 tests)
    ├── test_skills.py          # Skills engine unit tests (7 tests)
    ├── test_pipeline.py        # Scanner, synthesizer, builder, and research unit tests (10 tests)
    └── test_retry.py           # Gemini 503 retry and builder write-accounting tests (6 tests)
```

## Prerequisites

- Python 3.10+
- A Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

## Installation

1. Create and activate a Python virtual environment:

   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   # Or install in editable mode:
   pip install -e .
   ```

3. Configure your API key:

   ```bash
   # Copy example environment configuration
   cp .env.example .env
   # Edit .env and replace with your actual key:
   # GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

### 1. Autonomous Deep Research & Construction (`--build / -b`)

Trigger the full 5-stage research, dual-option synthesis, and construction workflow:

```bash
python main.py -b "Build a real-time Markdown live-preview component with code syntax highlighting"
```

### 2. Interactive Multi-Turn REPL (`--chat`)

Launch an ongoing design session where Aegis remembers previous turns:

```bash
python main.py --chat
```

REPL commands available during a session:

- `/build <goal>` — trigger autonomous deep research and construction from within the chat.
- `/skills` — list all discovered agent skills (local and global).
- `/skill <name>` — inspect full instructions for a specific agent skill (e.g. `/skill gemini-api-dev`).
- `/docs <query>` — search official Gemini API & SDK documentation (MCP).
- `/doc <chunk_id>` — retrieve specific Gemini documentation chunk (MCP).
- `/read <path>` — inspect a file locally with line numbers.
- `/grep <term>` — search repository code for functions or keywords.
- `/ls [path]` — display repository directory hierarchy.
- `/test` — run the unit test suite and view actual results.
- `/file <path>` — dynamically attach a repository file to the active conversation.
- `/clear` — reset conversational state and start a fresh context.
- `/history` — view turn count and active interaction ID.
- `/exit` — quit the console.

### 3. Single-Shot Query with Repository Context (`-f / --file`)

Pass specific files for Aegis to analyze:

```bash
python main.py -f main.py -f requirements.txt -i "Verify that this code conforms to Aegis Section 6 AI Feature Rules."
```

### 4. Local Developer Utilities (No API Key Required)

Execute local repository inspections, skill reads, and docs search directly via CLI flags:

```bash
# List all discovered agent skills
python main.py --skills

# View specific skill instructions
python main.py --skill gemini-api-dev

# Search official Gemini API & SDK documentation (MCP)
python main.py --docs "interactions api streaming"

# View clean repository file tree
python main.py --tree

# Search codebase for symbols
python main.py --grep DEFAULT_MODEL

# Run unit tests immediately
python main.py --run-tests
```

### 5. Custom Model & Thinking Controls

Customize model, thinking budget, and token limits (defaults to `gemini-3.8-flash`):

```bash
python main.py --model "models/gemini-3.8-flash" --thinking-level high --max-tokens 32768
```

To disable streaming and output the full response atomically:

```bash
python main.py --no-stream -i "Summarize database requirements."
```

## Testing

Run the automated test suite (67 unit tests):

```bash
python -m unittest discover -s tests -v
# Or using the built-in CLI shortcut:
python main.py --run-tests
```

## Security & Best Practices

- **MCP Streamable HTTP Handshake**: Docs tools run `initialize` + `notifications/initialized`, send `MCP-Protocol-Version`, and forward `Mcp-Session-Id` when the server issues one. Handshake failures fail open so `tools/call` still runs.
- **Path Traversal Protection**: `radulov.tools` and file attach (`-f` / `/file`) refuse paths outside the repository root. The builder also refuses `.env`, VCS, and credential targets.
- **Overwrite Guard**: The builder will not replace an existing file unless the chosen option listed it, and it never writes `main.py`, `AGENTS.md`, `radulov/`, `prompts/`, or packaging/CI paths.
- **Bounded Research Budget**: `radulov.researcher` enforces a hard 120-second timeout ceiling to prevent runaway latency.
- **Transient Gemini Retries**: `generate_content` calls retry `503 UNAVAILABLE` (and other 5xx) with exponential backoff. Quota `429` errors are not retried.
- **Red-Green-Verify Self-Correction**: `radulov.builder` executes tests immediately after writing code; if tests fail, it diagnoses and repairs the defect automatically before completion.
- **Never commit `.env`**: `.gitignore` is configured to block `.env` and credential files.
- **Untrusted Model Output**: In accordance with `AGENTS.md` and `aegis_system_prompt.md`, model output must be validated before applying destructive changes to codebases or production systems.
