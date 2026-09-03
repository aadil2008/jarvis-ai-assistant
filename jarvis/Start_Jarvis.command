#!/bin/zsh
cd "${0:A:h}"

ROOT="${0:A:h:h}"
if [[ -z "$JARVIS_ROUTER_URL" && -x "$ROOT/Start_Jarvis.command" ]]; then
  exec "$ROOT/Start_Jarvis.command"
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

"$PYTHON" main.py --voice
echo
read "REPLY?Press Return to close..."
