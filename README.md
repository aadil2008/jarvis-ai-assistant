# JARVIS-Inspired AI Desktop Assistant

A macOS-first voice and desktop assistant with two explicit setup choices:

- **Run locally:** Ollama chat, offline Whisper speech recognition, and your computer's voice. No API key; internet is needed once for downloads.
- **Use Groq API:** your Groq key powers chat and speech through a private local router. Internet is required; provider limits and charges may apply.

Setup remembers your choice. JARVIS never silently switches between local and cloud processing. Computer actions remain explicit local code; model output is never executed as a command.

> **Status:** working prototype. Local model selection uses conservative RAM estimates, not a guarantee of real-time voice performance.

## What works

### Desktop assistant

- Captures speech and transcribes it with offline Whisper or the selected Groq backend
- Detects installed and available RAM, recommends an Ollama model, and offers smaller alternatives
- Opens applications, websites, and local files
- Searches Google and YouTube
- Reads today's Apple Calendar events with permission
- Finds files in common folders
- Takes screenshots and controls system volume
- Keeps bounded conversation history during a session
- Speaks concise responses on macOS

### Optional Groq multi-model router

- Normal questions → `openai/gpt-oss-20b`
- Difficult reasoning → `openai/gpt-oss-120b`
- Coding → `qwen/qwen3.8-27b`
- Current web research → `groq/compound`
- Speech recognition → `whisper-large-v3-turbo`
- Manual route overrides without arbitrary model access
- Authentication, validation limits, bounded retry, safe fallback, and usage statistics

## Architecture

```text
User voice → microphone → chosen speech backend → JARVIS controller
                                                ├─ explicit local action
                                                └─ chosen chat backend → spoken reply
Local: offline Whisper + Ollama on 127.0.0.1:11434
Groq:  private loopback router → Groq speech/chat APIs
```

In Groq mode, the provider key belongs only to the router process. JARVIS
receives a separate random router credential. In local mode, audio stays in
memory and neither chat nor speech calls the cloud.

## Install on macOS or Windows

Use **Python 3.11–3.13** (3.12 recommended for audio package compatibility).

1. Download or clone this repository.
2. On macOS, double-click **Setup_Jarvis.command**. On Windows, double-click **Setup_Jarvis.bat**.
3. JARVIS asks **1. Locally with Ollama** or **2. Groq API**.
4. For local mode, install and open [Ollama](https://ollama.com/download), review the RAM recommendation, select a model, and approve the displayed download. Setup also downloads offline Whisper and checks both engines before saving settings.
5. For Groq mode, enter your own [Groq API key](https://console.groq.com/keys) at the hidden terminal prompt. Setup saves it in ignored `router/.env` and generates the private router secret. An existing key can be reused. No local model is downloaded.
6. Run **Start_Jarvis.command** or **Start_Jarvis.bat**. Allow microphone access when requested.

Type or say **setup**, or rerun the setup file, to change the backend; restart
JARVIS after saving. Cancelling leaves existing settings unchanged. The first
launch also asks for a backend if setup has not saved one yet.

The local recommendation starts at Qwen3 0.6B for 4 GB RAM, 1.7B for 8 GB,
4B for 16 GB, and 8B for 32 GB or more. Available memory can lower or block
that recommendation. These are JARVIS estimates with room for speech and the
OS, not Ollama's official minimum requirements. See [local setup details](docs/LOCAL_SETUP.md).

The Groq launcher binds a private router to a free loopback port, waits for
its health check, and stops it when JARVIS exits. Neither launcher starts a
public web server. Groq key authentication is checked on service use; saving
a key does not prove that it is active or has quota.

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

Automated tests use fake clients and consume no Groq quota. Install both
`jarvis/requirements-local.txt` and `router/requirements.txt` in your test
environment before running both suites.

```bash
python3 -m unittest discover -s jarvis/tests -v

cd router
python -m unittest discover -s tests -v
```

The suites cover local intent parsing, conversation isolation, authentication,
routing decisions, validation limits, model fallback rules, Whisper uploads,
standardized errors, usage statistics, and secret-safe connection failures.

## Security choices

- `.env`, local model settings, downloaded speech models, generated data, virtual environments, and credentials
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
- Local voice recognition is English-only in this setup.
- RAM does not determine latency by itself; CPU/GPU speed and other apps matter.
- Local answers do not have live web research. Explicit web searches still open online websites.
- Local chat uses a 2,048-token context and short conversation history.
- Windows launchers are provided; macOS-specific actions such as Apple Calendar remain macOS-only.
- Confirmation gates must be added before introducing sensitive or destructive
  actions.

## Next milestones

- Add permission-aware confirmations for higher-risk actions
- Add an optional wake-word engine without sending idle audio to a server
- Connect the architecture to Aegis, a bridge-risk prediction project
- Measure routing accuracy and end-to-end speech latency
