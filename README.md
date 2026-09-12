# RADULOV

Autonomous engineering intelligence and Gemini client interface configured with the **Aegis** system architecture.

## Repository Structure

```
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules for Python, virtualenvs, and secrets
├── AGENTS.md                   # Apex agent directives and operational governance
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── main.py                     # Entrypoint CLI runner for Gemini interactions
├── archive/
│   └── ai_studio_code.py       # Archived raw export from Google AI Studio
└── prompts/
    └── aegis_system_prompt.md  # Core Aegis engineering intelligence system prompt
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
   ```

3. Configure your API key:
   ```bash
   # Copy example environment configuration
   cp .env.example .env
   # Edit .env and replace with your actual key:
   # GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

### Interactive Mode
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

### Custom Model
Specify a different Gemini model using `--model` or `-m`:
```bash
python main.py --model "models/gemini-3.7-flash" --input "Analyze system invariants."
```

## Security & Best Practices

- **Never commit `.env`**: `.gitignore` is configured to block `.env` and credential files.
- **Model Output Validation**: Model output should be treated as untrusted input before applying to production environments or codebases.
