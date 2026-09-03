# Build Log

## 2023 — The question

Seeing Tony Stark build the Mark II suit with JARVIS raised a practical
question: what would it take to create an assistant that does more than answer
questions? Researching online "JARVIS" projects showed that many were voice
interfaces placed in front of a chatbot API.

## Early prototype — Useful lesson from failure

The first AI-assisted attempt could converse, but it did not reliably perform
computer actions and sometimes returned unrelated tutorial-style answers. The
idea was paused rather than presented as complete.

## 2025 — Local computer actions

With help from tools including Cursor, Google AntiGravity, ChatGPT, and Codex,
the assistant gained explicit handlers for applications, websites, file search,
calendar access, screenshots, and volume. Those actions remain deterministic:
model text is never executed as a system command.

## 2026 — Routing, speech, and testing

The project was separated into a desktop controller and a private router. The
router selects distinct models for conversation, reasoning, coding, current web
research, and Whisper speech recognition. Authentication, request limits,
bounded retries, and safe fallback rules were added with automated tests.

The desktop client now sends both conversation and recorded microphone audio
through the router. The Groq credential stays in the router process; JARVIS sees
only a separately revocable local router key.

## Current limitations

- This is a prototype, not a general autonomous agent.
- It has no always-listening wake word.
- Local actions are intentionally limited to explicit handlers.
- macOS permissions are required for microphone, calendar, screen capture, and
  some accessibility actions.
- Confirmation gates for future sensitive or destructive actions are still a
  planned feature.
