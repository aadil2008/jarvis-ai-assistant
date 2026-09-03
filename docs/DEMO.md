# 90-Second Portfolio Demo

This guide helps record an honest demonstration. Do not show `router/.env`, API
keys, private calendar details, or unrelated files in the recording.

## Before recording

1. Run `Setup_Jarvis.command` and configure `router/.env`.
2. Close private windows and clean the desktop.
3. Double-click `Start_Demo.command`. This starts the local router and JARVIS,
   and displays the selected route after AI answers.
4. Run `check` once. Confirm that the router and Whisper report `ready`.

## Suggested recording

**0:00–0:12 — The motivation**

> I wanted to understand what separates a voice chatbot from an assistant that
> can safely act on a real computer. JARVIS is my working experiment.

**0:12–0:30 — Voice and local action**

Say: `Open Notion Calendar.`

Explain that this command is parsed locally. A language model does not generate
or execute a shell command, and JARVIS reports success only after macOS accepts
the action.

**0:30–0:43 — File or web action**

Say one of these:

- `Find my calculus review.`
- `Search MIT robotics on YouTube.`

Use a prepared, non-private sample file if demonstrating file search.

**0:43–1:08 — Multi-model routing**

Ask two short questions:

- `Analyze the tradeoffs in allowing robots to make safety decisions.`
- `Write a Python function that checks whether a bridge sensor reading is outside a safe range.`

Point to the route line after each answer. The first should select the reasoning
route; the second should select the coding route.

**1:08–1:20 — Current web information**

Ask: `Research the latest AI robotics announcement online.`

Explain that current-information requests use the web-capable route and never
silently fall back to a model without web access.

**1:20–1:30 — Close**

> The project now separates deterministic computer actions, speech recognition,
> and AI reasoning. My next goal is to add permission-aware actions and connect
> the same architecture to Aegis, my bridge-risk project.

## Recording tips

- Use macOS screen recording and speak in your normal voice.
- Keep the terminal text large enough to read.
- Record one continuous take if possible.
- Do not edit out failures that reveal an important limitation; explain them.
- Upload the video where the application portal instructs, not as a large file
  committed to this repository.
