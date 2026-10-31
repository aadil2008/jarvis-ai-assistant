# JARVIS Desktop Client

This folder contains microphone input, conversation state, spoken output, and
explicit computer actions. Setup asks whether AI chat and speech should run locally (Ollama + offline
Whisper) or through the Groq router in the adjacent `router/` folder.

For the easiest macOS setup, use `Setup_Jarvis.command` and
`Start_Jarvis.command` in the repository root.

## Configuration

The selected mode and local model are stored in ignored `local_config.json`.
Re-run setup or use the `setup` command to change them. Optional overrides:

| Variable | Default | Purpose |
|---|---|---|
| `JARVIS_PROVIDER` | saved choice, otherwise local | Explicit `local` or `router` override |
| `JARVIS_ROUTER_URL` | `http://127.0.0.1:8000` | Router address |
| `JARVIS_ROUTER_API_KEY` | none | Revocable router credential |
| `JARVIS_ROUTER_TIMEOUT` | `75` | Request timeout in seconds |
| `JARVIS_SHOW_ROUTE` | false | Display selected route and model for demos |
| `JARVIS_SILENT` | false | Disable spoken output |

The desktop client does not load `GROQ_API_KEY` from a file. The launcher reads the router secret from `router/.env` and gives the client only
that secret. Local mode ignores router credentials and permits only the bundled
local model tags and loopback Ollama endpoint.

## Commands

- `open Safari`, `open Notion Calendar`, `open YouTube`, or `open report.pdf`
- `find report`
- `search college scholarships in Safari`
- `search MIT campus tour on YouTube`
- `check my calendar` to read today's Apple Calendar events
- `time`, `date`, `screenshot`, `minimize`, `volume up`, `volume down`, `mute`
- Ask questions naturally, such as `How are you?` or `Analyze this design`
- `mode text` or `mode voice`
- `check` to test the selected backend and show speech-file readiness
- `setup` to choose Groq or local mode; restart after saving
- `quit`

JARVIS indexes filenames only in Desktop, Documents, and Downloads when file
search is first used. It skips hidden and common development folders.

## Direct developer launch

For the saved backend, including automatic cloud router startup, run:

```bash
python launch.py --voice
```

For a separately managed router, start it first, then run:

```bash
export JARVIS_PROVIDER=router
export JARVIS_ROUTER_API_KEY="the_router_secret"
python main.py --voice
```

Use `--text` for keyboard input, `--silent` to suppress speech, or `--diagnose`
for a readiness check. `python setup_local.py --recommend` prints RAM advice
without downloads or configuration changes. See [local setup](../docs/LOCAL_SETUP.md).

## macOS permissions

The microphone requires Microphone permission. Calendar, screenshots, or window
control can also require permission under **System Settings > Privacy &
Security**. JARVIS reports a failed action instead of telling the model to
pretend it succeeded.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The desktop tests do not contact Groq or change the computer.
