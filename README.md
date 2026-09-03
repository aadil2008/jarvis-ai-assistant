# JARVIS-Inspired AI Desktop Assistant

A macOS-first voice and desktop assistant connected to a secure, deterministic
multi-model AI router. The project began with one question: how could an
assistant move beyond a voice-enabled chatbot and perform useful actions on a
real computer?

> **Status:** working prototype. Voice transcription and AI conversation now
> travel through the router, while computer actions remain explicit local code.
> The limitations below are intentional and documented.

## What works

### Desktop assistant

- Captures speech and transcribes it with Whisper through the private router
- Opens applications, websites, and local files
- Searches Google and YouTube
- Reads today's Apple Calendar events with permission
- Finds files in common folders
- Takes screenshots and controls system volume
- Keeps bounded conversation history during a session
- Speaks concise responses on macOS

### Multi-model router

- Normal questions → `openai/gpt-oss-20b`
- Difficult reasoning → `openai/gpt-oss-120b`
- Coding → `qwen/qwen3.8-27b`
- Current web research → `groq/compound`
- Speech recognition → `whisper-large-v3-turbo`
- Manual route overrides without arbitrary model access
- Authentication, validation limits, bounded retry, safe fallback, and usage statistics

## Architecture

```text
User voice
    │
    ▼
JARVIS desktop controller
    ├── Safe local command ──► explicit macOS action ──► confirmed result
    │
    ├── Recorded WAV ────────► /v1/transcribe ────────► Whisper V3 Turbo
    │
    └── AI request ──────────► /v1/chat
                                  ├── Normal ─────────► GPT-OSS 20B
                                  ├── Reasoning ──────► GPT-OSS 120B
                                  ├── Coding ─────────► Qwen 3.8 27B
                                  └── Current web ────► Groq Compound
```

The Groq API key belongs only to the router process. JARVIS receives a separate,
revocable router key. Model responses are never executed as system commands.

## Quick start on macOS

Python 3.11 or later is required.

1. Double-click `Setup_Jarvis.command` once.
2. Open `router/.env` and replace both placeholders:
   - `GROQ_API_KEY` receives the Groq key.
   - `ROUTER_API_KEY` receives a different random secret.
3. Double-click `Start_Jarvis.command`.
4. Allow microphone and other requested macOS permissions.

Generate the router secret with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

The combined launcher starts the router only on `127.0.0.1`, waits for its
health check, passes only the router key to JARVIS, and shuts the router down
when JARVIS exits.

## Repository structure

```text
jarvis/   Voice input, conversation state, and deterministic computer actions
router/   FastAPI model router, Groq client, tests, and Docker support
docs/     Build history and a short portfolio-demo recording guide
```

See [`jarvis/README.md`](jarvis/README.md),
[`router/README.md`](router/README.md), and
[`docs/DEMO.md`](docs/DEMO.md) for details.

## Tests

All automated tests use fake clients and consume no Groq quota.

```bash
python3 -m unittest discover -s jarvis/tests -v

cd router
python -m unittest discover -s tests -v
```

The suites cover local intent parsing, conversation isolation, authentication,
routing decisions, validation limits, model fallback rules, Whisper uploads,
standardized errors, usage statistics, and secret-safe connection failures.

## Security choices

- `.env`, `api_key.txt`, generated data, virtual environments, and credentials
  are excluded from Git.
- The desktop client does not receive the Groq key.
- The router does not log prompts, authorization headers, or API keys.
- Computer actions use explicit handlers; AI output is not run as shell code.
- Current web requests never silently fall back to a non-web model.

## Development process

The first prototype could answer questions but behaved like a generic chatbot
and sometimes claimed it could not control applications. The design was then
split into three testable responsibilities: local actions, model routing, and
speech recognition. See the [build log](docs/BUILD_LOG.md) for the development
timeline and the failures that shaped this architecture.

Development was AI-assisted using ChatGPT, Cursor, Google AntiGravity, and
Codex. Requirements, testing, iteration, and final technical decisions were
directed and reviewed by the project creator.

## Honest limitations

- This is a student-built prototype, not Tony Stark's fictional JARVIS.
- It has no always-listening wake word.
- It deliberately supports a limited set of local actions.
- Some actions require macOS privacy permissions.
- Confirmation gates must be added before introducing sensitive or destructive
  actions.

## Next milestones

- Add permission-aware confirmations for higher-risk actions
- Add an optional wake-word engine without sending idle audio to a server
- Connect the architecture to Aegis, a bridge-risk prediction project
- Measure routing accuracy and end-to-end speech latency
