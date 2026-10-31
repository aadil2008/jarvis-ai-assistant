# Choosing how JARVIS runs

Setup presents two choices and remembers the user's selection in
`jarvis/local_config.json`. Use the same setup again, or type `setup` within
JARVIS, to switch; restart after saving. There is no automatic cloud fallback.

| Mode | Chat | Speech recognition | Needs |
| --- | --- | --- | --- |
| Local | Ollama on this computer | faster-whisper, CPU int8 | RAM, disk space, Ollama; internet for initial downloads |
| Groq API | Private local router to Groq | Groq Whisper | Your own API key and internet; provider usage limits apply |

Replies use macOS `say` or Windows' installed system voice. This is turn-based
voice input, not an always-listening wake word. Microphone permission is still
required. Local speech is English-only. Explicit website/search commands use
the internet even in local mode; local AI has no current web-research tools.

## RAM recommendations

| Installed RAM starting tier | Ollama model | Approximate model download | Offline speech |
| --- | --- | --- | --- |
| Under 4 GiB | No recommendation | — | — |
| 4–7.9 GiB | `qwen3:0.6b` | 0.523 GB | `tiny.en` |
| 8–15.9 GiB | `qwen3:1.7b` | 1.4 GB | `tiny.en` |
| 16–31.9 GiB | `qwen3:4b` | 2.5 GB | `base.en` |
| 32 GiB and above | `qwen3:8b` | 5.2 GB | `base.en` |

RAM tiers are **JARVIS estimates**, not official Ollama minimum requirements.
They deliberately favor smaller models for voice use. The installer also
checks currently available memory, reserves 2 GiB of total RAM for the OS and
1 GiB of available memory for other activity, and accounts for the local speech
model and a 2,048-token chat context. Busy computers may receive a smaller
recommendation or a request to close other apps. Failure to detect RAM does not
produce a guessed recommendation. RAM numbers use GiB; download sizes use GB.

RAM is not a speed benchmark. CPU/GPU, memory pressure, model versions and other
processes affect latency. No GPU memory detection or real-time guarantee is
claimed. Whisper requires up to approximately 0.2 GB extra download. Disk
checks include extra headroom; existing model data is never deleted to free space.

Model tags and approximate download sizes were checked against Ollama's
[0.6B](https://ollama.com/library/qwen3:0.6b),
[1.7B](https://ollama.com/library/qwen3:1.7b),
[4B](https://ollama.com/library/qwen3:4b), and
[8B](https://ollama.com/library/qwen3:8b) pages on October 31, 2026.
The runtime caps context explicitly because [context consumes memory](https://docs.ollama.com/faq).

## Local setup and recovery

Install Python 3.11–3.13 (3.12 recommended), then run the setup file for your OS.
Select local mode. Install/open [Ollama](https://ollama.com/download) if needed;
JARVIS gives this link rather than running a downloaded system installer.
Select the recommended model or a listed smaller alternative. Model files download only
after you confirm the model download prompt (Python packages install earlier). Ollama shows pull progress.

Setup installs the [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
speech files under `jarvis/models/`, loads them, and checks a local Ollama reply.
Only then does it save a working configuration. Failed or interrupted downloads
leave the previous settings intact; rerun setup to retry. Declining downloads
leaves setup incomplete for a new user, rather than marking it ready.

On later launches, missing Ollama, a missing model, timeout, or damaged speech
files produces an actionable message. JARVIS does not send the request to Groq
as a fallback. Speech loading uses `local_files_only=True`; recordings stay in
memory, and the speech engine is loaded once per session. Chat requests ignore
HTTP proxies and redirects, use fixed loopback, and only allow the listed local
model names. These safeguards apply to JARVIS's inference path; Ollama can still
perform its own software update checks.

Run this without downloading or changing anything:

```bash
# From repository root, after setup installed the local dependencies:
jarvis/.venv/bin/python jarvis/setup_local.py --recommend
# Windows:
jarvis\.venv\Scripts\python.exe jarvis\setup_local.py --recommend
```

## Groq setup and recovery

Choose Groq API. The key prompt is hidden. A separate router secret is generated
automatically, and both keys go into ignored `router/.env`; on POSIX this file is
owner-readable/writable only. Key format is checked, not provider authentication.
A disabled/expired key or exhausted quota will be reported when using Groq.
No Ollama or Whisper model download occurs for this choice.

The launcher starts the router privately on a free loopback port and shuts it
down on exit. The desktop process receives the router credential, not the Groq
key. On Windows the file inherits the user's directory ACL; keep the checkout
inside your own account. Re-run setup to replace a key or change modes.
