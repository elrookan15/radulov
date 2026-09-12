# RADULOV

[![CI](https://github.com/elrookan15/radulov/actions/workflows/ci.yml/badge.svg)](https://github.com/elrookan15/radulov/actions/workflows/ci.yml)

Autonomous engineering intelligence and Gemini client interface configured with the **Aegis** system architecture.

## Repository Structure

```
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI matrix (Python 3.10, 3.11, 3.12)
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules for Python, virtualenvs, and secrets
├── AGENTS.md                   # Apex agent directives and operational governance
├── README.md                   # Project documentation
├── pyproject.toml              # PEP 621 packaging & linter configuration
├── requirements.txt            # Python dependencies
├── main.py                     # Entrypoint CLI runner with streaming support
├── archive/
│   └── ai_studio_code.py       # Archived raw export from Google AI Studio
├── prompts/
│   └── aegis_system_prompt.md  # Core Aegis engineering intelligence system prompt
└── tests/
    └── test_main.py            # Unit test suite
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

### Interactive Mode (Real-Time Streaming)
Run without arguments to prompt interactively:
```bash
python main.py
```

### CLI Flag Mode
Pass the prompt directly via `--input` or `-i`:
```bash
python main.py --input "Design the authentication architecture for RADULOV."
```

### Pipe Mode
Pipe prompt text via stdin:
```bash
cat task.txt | python main.py
```

### Custom Model & Thinking Controls
Customize model, thinking budget, and token limits:
```bash
python main.py --model "models/gemini-3.7-flash" --thinking-level high --max-tokens 32768
```

To disable streaming and output the full response at once:
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
- **Model Output Validation**: Model output should be treated as untrusted input before applying to production environments or codebases.
