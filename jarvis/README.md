# JARVIS

JARVIS is a cross-platform personal voice and desktop assistant. Its local commands work without an API key. General conversation uses OpenAI or Groq when configured.

## macOS setup

1. Double-click `Setup_Jarvis.command` once.
2. Double-click `Start_Jarvis.command` whenever you want to start Jarvis.
3. Allow Microphone access when macOS asks. Opening apps and controlling the computer may also require Accessibility permission in **System Settings > Privacy & Security**.

If macOS blocks a command file, Control-click it, select **Open**, and confirm.

## Windows setup

1. Double-click `Setup_Jarvis.bat` once.
2. Double-click `Start_Jarvis.bat` whenever you want to start Jarvis.

## Optional AI answers

Local commands such as `open`, `find`, `time`, and `screenshot` do not need an API key.

For AI answers, either set `OPENAI_API_KEY` or `GROQ_API_KEY`, or copy `api_key.example.txt` to `api_key.txt` and replace its contents with one key. Never share or commit `api_key.txt`.

Jarvis automatically recognizes Groq keys beginning with `gsk_`, connects to Groq's OpenAI-compatible endpoint, and uses the production model `openai/gpt-oss-20b`. You do not need to change the code.

An API key also needs available API credits. A ChatGPT subscription and OpenAI API billing are separate.

The default model is `gpt-4o-mini`. You can select another model available to your API project with the `JARVIS_MODEL` environment variable.

## Commands

- `open Safari`, `open Notion Calendar`, `open YouTube`, or `open report.pdf`
- `find report`
- `search college scholarships in Safari`
- `search MIT campus tour on YouTube`
- `check my calendar` to read today's Apple Calendar events
- `time`, `screenshot`, `minimize`, `volume up`, `volume down`, `mute`
- Ask questions naturally, such as `How are you?` or `Explain quantum computing briefly`
- `mode text` or `mode voice`
- `check` to see which features are ready
- `quit`

Jarvis indexes filenames only in Desktop, Documents, and Downloads when you first use `find` or try to open a file. It skips hidden folders and common development folders.
