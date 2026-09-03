# JARVIS Desktop Client

This folder contains microphone input, conversation state, spoken output, and
explicit computer actions. AI chat and Whisper transcription go through the
router in the adjacent `router/` folder.

For the easiest macOS setup, use `Setup_Jarvis.command` and
`Start_Jarvis.command` in the repository root.

## Configuration

The client reads only these optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `JARVIS_ROUTER_URL` | `http://127.0.0.1:8000` | Router address |
| `JARVIS_ROUTER_API_KEY` | none | Revocable router credential |
| `JARVIS_ROUTER_TIMEOUT` | `75` | Request timeout in seconds |
| `JARVIS_SHOW_ROUTE` | false | Display selected route and model for demos |
| `JARVIS_SILENT` | false | Disable spoken output |

The desktop client does not load `GROQ_API_KEY` from a file. The combined root
launcher reads the router secret from `router/.env` and gives the client only
that secret.

## Commands

- `open Safari`, `open Notion Calendar`, `open YouTube`, or `open report.pdf`
- `find report`
- `search college scholarships in Safari`
- `search MIT campus tour on YouTube`
- `check my calendar` to read today's Apple Calendar events
- `time`, `date`, `screenshot`, `minimize`, `volume up`, `volume down`, `mute`
- Ask questions naturally, such as `How are you?` or `Analyze this design`
- `mode text` or `mode voice`
- `check` to test the router and show local readiness
- `quit`

JARVIS indexes filenames only in Desktop, Documents, and Downloads when file
search is first used. It skips hidden and common development folders.

## Direct developer launch

Start the router first, then run:

```bash
export JARVIS_ROUTER_API_KEY="the_router_secret"
python main.py --voice
```

Use `--text` for keyboard input, `--silent` to suppress speech, or `--diagnose`
for a readiness check.

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
