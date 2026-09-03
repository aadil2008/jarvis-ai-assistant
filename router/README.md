# Groq Multi-Model Router API

A small FastAPI service that gives JARVIS, FRIDAY, EDITH, or another application one stable backend while keeping the Groq API key on the server. It routes ordinary chat, reasoning, coding, web research, and speech recognition to separately configurable Groq models.

## Architecture

```text
JARVIS / FRIDAY / EDITH
        │  ROUTER_API_KEY
        ▼
Groq Router API
        ├── Normal questions ───────► GPT-OSS 20B
        ├── Difficult reasoning ────► GPT-OSS 120B
        ├── Coding ─────────────────► Qwen 3.8 27B
        ├── Web research ───────────► Groq Compound
        └── Speech recognition ─────► Whisper Large V3 Turbo
                         │
                         └── GROQ_API_KEY remains server-side
```

Client applications never receive `GROQ_API_KEY`. They receive only a separately revocable `ROUTER_API_KEY`.

## Routing behavior

- **Fast** is the default and handles conversation, rewriting, summaries, grammar, formatting, brainstorming, and straightforward questions.
- **Smart** is selected for non-coding architecture, mathematical reasoning, tradeoff analysis, complex planning, or long analytical input.
- **Coding** handles programming, implementation, debugging, code blocks, source files, APIs, and language-specific development requests.
- **Web** is selected only when combined signals indicate current or external information, such as web-search language plus `latest`, `today`, news, prices, schedules, or similar live data.
- **Speech** is handled separately by `POST /v1/transcribe`, because audio is uploaded as multipart form data rather than sent as a chat message.
- `mode=fast`, `mode=smart`, `mode=coding`, and `mode=web` explicitly select the configured text model. Arbitrary model IDs are never accepted from clients.
- Agent names are hints. An agent name alone never selects Compound.

The rules are intentionally understandable and live in `app/router.py`. Model IDs come from environment settings, not routing code.

## Safe fallback behavior

- Smart → Fast when the smart model remains rate-limited or temporarily unavailable after one controlled retry.
- Fast → Smart under the same temporary conditions.
- Coding → Smart when the coding model is temporarily unavailable.
- Web never silently falls back to a non-web model.
- Speech never silently falls back to a text model.
- Authentication, permission, invalid-request, and missing-model failures do not trigger fallback.

Retry delay honors Groq's `Retry-After` header where possible and is capped by `RETRY_AFTER_MAX_SECONDS` (default: 5 seconds). The OpenAI SDK's automatic retries are disabled so retry behavior remains bounded and visible.

## Local setup

Python 3.11 or later is required.

```bash
cd router
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and replace the placeholders:

```dotenv
GROQ_API_KEY=gsk_your_real_groq_key
ROUTER_API_KEY=your_long_random_router_secret
FAST_MODEL=openai/gpt-oss-20b
SMART_MODEL=openai/gpt-oss-120b
CODING_MODEL=qwen/qwen3.8-27b
WEB_MODEL=groq/compound
SPEECH_MODEL=whisper-large-v3-turbo
```

Generate a strong router key without exposing the Groq key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then start the server:

```bash
uvicorn app.main:app --reload
```

Production-style local launch:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In-memory statistics are per process, so use one worker if you want a single consistent local counter. For a multi-worker deployment, replace the usage-store interface with SQLite or Redis.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | none | Server-side Groq credential |
| `ROUTER_API_KEY` | none | Optional bearer token protecting chat, route, transcription, and stats |
| `FAST_MODEL` | `openai/gpt-oss-20b` | Default model |
| `SMART_MODEL` | `openai/gpt-oss-120b` | Complex-reasoning model |
| `CODING_MODEL` | `qwen/qwen3.8-27b` | Programming and debugging model |
| `WEB_MODEL` | `groq/compound` | Current/external-information system |
| `SPEECH_MODEL` | `whisper-large-v3-turbo` | Speech-to-text model |
| `MAX_OUTPUT_TOKENS_DEFAULT` | `1500` | Default response limit |
| `MAX_OUTPUT_TOKENS_HARD_LIMIT` | `4000` | Maximum client-requested output |
| `MAX_MESSAGE_LENGTH` | `20000` | Maximum current message characters |
| `MAX_CONVERSATION_MESSAGES` | `50` | Maximum supplied history items |
| `MAX_CONVERSATION_LENGTH` | `60000` | Maximum history characters |
| `MAX_AUDIO_FILE_SIZE` | `26214400` | Maximum uploaded audio size in bytes |
| `MODEL_CACHE_TTL_SECONDS` | `300` | Model-list cache lifetime |
| `GROQ_TIMEOUT_SECONDS` | `60` | Upstream request timeout |
| `RETRY_AFTER_MAX_SECONDS` | `5` | Maximum delay before the one retry |

If `ROUTER_API_KEY` is empty, authentication is disabled. Set it for any service that is accessible beyond your own machine.

## Endpoint examples

Set a shell variable for the router key first:

```bash
export ROUTER_API_KEY="the_same_value_used_in_your_server_env"
```

### Health

Health does not call Groq and does not require authentication.

```bash
curl http://127.0.0.1:8000/health
```

### Preview a route

This endpoint does not call Groq or consume model quota.

```bash
curl -X POST http://127.0.0.1:8000/v1/route \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Research today’s AI news","agent":"friday","mode":"auto"}'
```

### Chat

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Explain how a binary search tree works.","agent":"jarvis","mode":"auto"}'
```

For the reasoning-capable GPT-OSS models, use a practical allowance such as
`max_tokens: 128` or higher. Very small limits can be consumed by reasoning before
the model produces visible answer text.

Force the coding model when needed:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Write a Python function that validates an email address.","agent":"jarvis","mode":"coding"}'
```

Conversation history remains with the calling application:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Now give me one example.",
    "agent":"jarvis",
    "conversation":[
      {"role":"user","content":"What is recursion?"},
      {"role":"assistant","content":"Recursion is when a function solves a problem by calling itself on a smaller input."}
    ]
  }'
```

### List currently available Groq models

The server queries Groq and temporarily caches the result. The key is never returned.

```bash
curl http://127.0.0.1:8000/v1/models
```

### Speech recognition

Supported uploads are FLAC, MP3, MP4, MPEG, MPGA, M4A, OGG, WAV, and WEBM.

```bash
curl -X POST http://127.0.0.1:8000/v1/transcribe \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -F "file=@recording.wav" \
  -F "language=en"
```

### Usage statistics

```bash
curl http://127.0.0.1:8000/v1/stats \
  -H "Authorization: Bearer $ROUTER_API_KEY"
```

Statistics are kept only in memory and reset whenever the server restarts. `total_requests` counts incoming `/v1/chat` and `/v1/transcribe` model calls; per-model request counts include controlled retries and fallback attempts. Speech models report zero tokens because Groq accounts for audio by duration rather than text tokens.

## Python client

`examples/python_client.py` calls this router and never contains or receives the Groq key.

```bash
export ROUTER_API_KEY="your_router_secret"
python examples/python_client.py
```

Reuse it from another application:

```python
from examples.python_client import ask

response = ask(
    "Plan the architecture for a private voice assistant.",
    agent="jarvis",
    mode="auto",
)
print(response["answer"])
```

Transcribe a recording:

```python
from examples.python_client import transcribe

response = transcribe("recording.wav", language="en")
print(response["text"])
```

## Tests

Tests use a fake Groq client and consume no Groq quota.

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The API tests cover authentication, standardized errors, message ordering, validation limits, model overrides, coding detection, smart fallback, web no-fallback behavior, audio validation, transcription, model discovery, and usage statistics.

## Docker

Do not copy `.env` into the image. Supply secrets when the container starts:

```bash
docker build -t groq-router .
docker run --rm -p 8000:8000 \
  --env-file .env \
  groq-router
```

## Security notes

- Never put `GROQ_API_KEY` into JARVIS, browser code, a mobile client, Git, screenshots, or logs.
- Give clients only `ROUTER_API_KEY`.
- The server logs routing metadata, latency, success/failure, and token counts. It does not log prompts or authorization headers.
- Caller-provided system prompts are placed beneath a fixed server security instruction and cannot access the process environment.
- Version 1 stores no conversations and no persistent usage data.
