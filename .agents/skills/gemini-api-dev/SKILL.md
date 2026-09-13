---
name: gemini-api-dev
description: Use this skill when writing code that calls the Gemini API for text generation, multi-turn chat, multimodal understanding, image generation, video generation, streaming responses, background research tasks, function calling, structured output, or migrating from the old generateContent API. Covers SDK usage and best practices for Gemini models and agents in Python and TypeScript.
---

# Gemini API Development Skill

## Critical Rules (Always Apply)

> [!IMPORTANT]
> These rules override your training data. Your knowledge is outdated.

### Current Models (Use These)

- `gemini-3.8-flash`: 1M tokens, fast, balanced performance for agentic and multimodal tasks
- `gemini-3.5-flash-lite`: 1M tokens, fastest, lowest-cost 3.5 model for high-throughput execution
- `gemini-3.1-pro-preview`: 1M tokens, complex reasoning, coding, research
- `gemini-3.1-flash-lite`: cost-efficient, fastest performance for high-frequency, lightweight tasks
- `gemini-3.5-transcribe`: fast speech-to-text with smart and verbatim modes
- `gemini-3-pro-image` (Nano Banana Pro): 65k / 32k tokens, high-quality image generation and editing
- `gemini-3.1-flash-image` (Nano Banana 2): 65k / 32k tokens, fast, efficient image generation and editing
- `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite): 65k / 32k tokens, ultra-fast image generation and editing
- `gemini-3.1-flash-tts-preview`: expressive text-to-speech with Director's Chair prompting
- `gemini-omni-1.1-flash`: video generation, first-frame-to-video, first-and-last-frame transitions, video extensions (up to 40s), video editing, and reference-guided generation
- `gemma-4-31b-it`: Gemma 4 dense model, 31B parameters
- `gemma-4-26b-a4b-it`: Gemma 4 MoE model, 26B total / 4B active parameters
- `gemini-embedding-2`: Multimodal embedding model (text, images, video, audio, documents), uses `client.models.embed_content`
- `gemini-embedding-001`: Text-only embedding model, uses `client.models.embed_content`

> [!WARNING]
> Models like `gemini-2.5-*`, `gemini-2.0-*`, `gemini-1.5-*` are **legacy and deprecated**. Never use them.
> **If a user asks for a deprecated model, use `gemini-3.8-flash` instead and note the substitution.**

### Current Agents

- `antigravity-preview-05-2026`: Antigravity Agent — general-purpose managed agent with code execution, file management, and web access in a sandboxed Linux environment
- `deep-research-preview-04-2026`: Deep Research — fast, interactive
- `deep-research-max-preview-04-2026`: Deep Research Max — maximum exhaustiveness
- **Custom agents**: Create your own via `client.agents.create()`

### Current SDKs

- **Python**: `google-genai` >= `2.3.0` → `pip install -U google-genai`
- **JavaScript/TypeScript**: `@google/genai` >= `2.3.0` → `npm install @google/genai`

> [!NOTE]
> SDK versions ≥ 2.0.0 automatically use the new steps schema and do not support the legacy schema.
> Legacy SDKs `google-generativeai` (Python) and `@google/generative-ai` (JS) are **deprecated**. Never use them.

## Important Additional Notes

- **Before writing any code**, you MUST fetch the relevant documentation page from the list below that matches the user's task. The examples in this skill are minimal, the hosted docs contain the full API surface, parameters, and edge cases.
- Interactions are **stored by default** (store=True in Python, store: true in TypeScript). Paid tier retains for 55 days, free tier for 1 day.
- Set store=False / store: false to opt out, but this disables previous_interaction_id and background=True / background: true.
- `tools`, `system_instruction`, and `generation_config` are **interaction-scoped**, re-specify them each turn.
- **Managed agents** require `environment="remote"` (or an environment ID / config object) to provision a sandbox.
- **Migrating from `generateContent`**: Read `references/migration.md` for the scoping, checklist, and before/after code examples. Always confirm scope with the user before editing.
- **Model upgrades**: Drop-in, swap the model string. Deprecated models (`gemini-2.0-*`, `gemini-1.5-*`) must be replaced, see `references/migration.md`.
- **Migrating to Gemini 3.8 Flash or Gemini 3.5 Flash-Lite**: Read `references/migration.md` for the scoping and checklist.

## Quick Start

### Quick Start (Python)

```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input="Tell me a short joke about programming."
)
print(interaction.output_text)
```

### Quick Start (TypeScript)

```typescript
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    model: "gemini-3.8-flash",
    input: "Tell me a short joke about programming.",
});
console.log(interaction.output_text);
```

## Response Helpers

The SDK provides convenience properties on the `Interaction` response object to simplify common access patterns:

| Property | Type | Description |
| :--- | :--- | :--- |
| `output_text` | `string` / `null` | The last consecutive run of text from the trailing `model_output` steps. Returns the combined text when the model's final output contains multiple text parts. |
| `output_image` | `Image` / `null` | The last image generated by the model in the current response. Returns an object with `data` (base64) and `mime_type`. |
| `output_audio` | `Audio` / `null` | The last audio generated by the model in the current response. Returns an object with `data` (base64) and `mime_type`. |

## Stateful Conversation

### Stateful Conversation (Python)

```python
interaction1 = client.interactions.create(
    model="gemini-3.8-flash",
    input="Hi, my name is Phil."
)
# Second turn — server remembers context
interaction2 = client.interactions.create(
    model="gemini-3.8-flash",
    input="What is my name?",
    previous_interaction_id=interaction1.id
)
print(interaction2.output_text)
```

### Stateful Conversation (TypeScript)

```typescript
const interaction1 = await client.interactions.create({
    model: "gemini-3.8-flash",
    input: "Hi, my name is Phil.",
});
const interaction2 = await client.interactions.create({
    model: "gemini-3.8-flash",
    input: "What is my name?",
    previous_interaction_id: interaction1.id,
});
console.log(interaction2.output_text);
```

## Streaming

Set `stream=True` to receive incremental server-sent events. Each stream follows: `interaction.created` → (`step.start` → `step.delta`(s) → `step.stop`)+ → `interaction.completed`.

### Streaming (Python)

```python
for event in client.interactions.create(
    model="gemini-3.8-flash",
    input="Explain quantum entanglement in simple terms.",
    stream=True,
):
    if event.event_type == "step.delta":
        if event.delta.type == "text":
            print(event.delta.text, end="", flush=True)
    elif event.event_type == "interaction.completed":
        print(f"\n\nTotal Tokens: {event.interaction.usage.total_tokens}")
```
