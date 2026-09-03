# JARVIS-Inspired AI Desktop Assistant

A macOS-first voice and desktop assistant paired with a secure, deterministic
multi-model AI router. The project began as an attempt to understand how an
assistant like JARVIS could move beyond a voice-enabled chatbot and perform
useful actions on a real computer.

> **Current status:** active development. The desktop assistant and the
> multi-model router both work independently. Connecting every desktop AI and
> speech request through the router is the next milestone. The repository does
> not claim that unfinished integration is complete.

## What works now

### Desktop assistant

- Voice and text interaction
- Natural spoken responses on macOS
- Opens applications, websites, and local files
- Searches Google and YouTube
- Reads today's Apple Calendar events with permission
- Finds files in common folders
- Takes screenshots and controls system volume
- Keeps short conversation history during a session

### Multi-model router

- Normal questions → `openai/gpt-oss-20b`
- Difficult reasoning → `openai/gpt-oss-120b`
- Coding → `qwen/qwen3.8-27b`
- Current web research → `groq/compound`
- Speech recognition → `whisper-large-v3-turbo`
- Manual route overrides without arbitrary model access
- Authentication, validation limits, bounded retry, safe fallback, and usage statistics
- 34 mocked unit/API tests plus successful live checks of every configured model role

## Architecture

```text
User voice
    │
    ▼
JARVIS desktop controller
    ├── Safe local command ──► macOS action ──► confirmed result
    │
    ├── Recorded audio ──────► /v1/transcribe ──► Whisper V3 Turbo
    │
    └── AI request ──────────► /v1/chat
                                  ├── Normal ───► GPT-OSS 20B
                                  ├── Reasoning ► GPT-OSS 120B
                                  ├── Coding ───► Qwen 3.8 27B
                                  └── Web ──────► Groq Compound
```

The Groq API key belongs only on the router server. JARVIS receives a separate,
revocable router key.

## Repository structure

```text
jarvis/   Desktop voice assistant and local Mac actions
router/   FastAPI multi-model router, tests, Dockerfile, and client example
```

See [`jarvis/README.md`](jarvis/README.md) and [`router/README.md`](router/README.md)
for setup and usage instructions.

## Test the router

```bash
cd router
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

## Security

- Never commit `.env`, `api_key.txt`, or access tokens.
- Never embed the Groq key in the desktop application.
- The router does not log prompts, authorization headers, or API keys.
- Computer actions use explicit local handlers; model text is not executed as shell code.

## Development process

The first prototype could answer questions but behaved like a generic chatbot
and sometimes claimed that it could not control applications. The project was
then separated into three responsibilities: local actions, model routing, and
speech recognition. This made each part easier to test and prevented the AI
model from falsely claiming that an action succeeded.

Development was AI-assisted using ChatGPT, Cursor, Google AntiGravity, and
Codex. Requirements, testing, iteration, and final technical decisions were
directed and reviewed by the project creator.

## Next milestones

- Route the desktop assistant's AI requests through the router
- Replace Google speech recognition with the Whisper endpoint
- Add explicit confirmation before sensitive or destructive actions
- Record a concise end-to-end demonstration
- Add process screenshots and a development timeline
