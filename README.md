# RADULOV

[![CI](https://github.com/elrookan15/radulov/actions/workflows/ci.yml/badge.svg)](https://github.com/elrookan15/radulov/actions/workflows/ci.yml)

Autonomous engineering intelligence and Gemini client interface configured with the **Aegis** system architecture.

## Features

- **Aegis Architecture Governance**: Grounded by [prompts/aegis_system_prompt.md](prompts/aegis_system_prompt.md) and [AGENTS.md](AGENTS.md).
- **Stateful Multi-Turn REPL (`--chat`)**: Interactive console remembering context turns via Gemini Interactions server-side state.
- **Repository File Context Injection (`-f / --file`)**: Attach local source files directly into model reasoning context.
- **Real-Time Streaming**: Incremental token delivery via `step.delta` events with `--no-stream` fallback.
- **Hyperparameter Controls**: Configurable thinking budget (`--thinking-level`), token limits (`--max-tokens`), and model targets (`--model`).
- **Session Audit Logging**: Transcripts automatically recorded to local `.radulov/sessions/` (ignored by Git).
- **Automated CI Matrix**: GitHub Actions verifying Python 3.10, 3.11, and 3.12 across all pushes and PRs.

## Repository Structure

```
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI matrix (Python 3.10, 3.11, 3.12)
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules for Python, virtualenvs, sessions, and secrets
├── AGENTS.md                   # Apex agent directives and operational governance
├── README.md                   # Project documentation
├── pyproject.toml              # PEP 621 packaging & linter configuration
├── requirements.txt            # Python dependencies
├── main.py                     # Entrypoint CLI runner with streaming and multi-turn REPL
├── archive/
│   └── ai_studio_code.py       # Archived raw export from Google AI Studio
├── prompts/
│   └── aegis_system_prompt.md  # Core Aegis engineering intelligence system prompt
└── tests/
    └── test_main.py            # Unit test suite (8 tests)
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

### 1. Interactive Multi-Turn REPL (`--chat`)
Launch an ongoing design session where Aegis remembers previous turns:
```bash
python main.py --chat
```
REPL commands available during a session:
- `/file <path>` — dynamically attach a repository file to the active conversation.
- `/clear` — reset conversational state and start a fresh context.
- `/history` — view turn count and active interaction ID.
- `/exit` — quit the console.

### 2. Single-Shot Query with Repository Context (`-f / --file`)
Pass specific files for Aegis to analyze:
```bash
python main.py -f main.py -f requirements.txt -i "Review this CLI architecture for security and edge cases."
```

### 3. Pipe Mode
Pipe prompt text or logs via stdin:
```bash
git diff | python main.py -i "Review this git diff according to Aegis code generation standards."
```

### 4. Custom Model & Thinking Controls
Customize model, thinking budget, and token limits:
```bash
python main.py --model "models/gemini-3.7-flash" --thinking-level high --max-tokens 32768
```

To disable streaming and output the full response atomically:
```bash
python main.py --no-stream -i "Summarize database requirements."
```

## Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests -v
```

## Security & Best Practices

- **Never commit `.env`**: `.gitignore` is configured to block `.env` and credential files.
- **Untrusted Model Output**: In accordance with `AGENTS.md` and `aegis_system_prompt.md`, model output must be validated before applying destructive changes to codebases or production systems.
