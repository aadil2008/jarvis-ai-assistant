#!/bin/zsh
ROOT="${0:A:h}"
JARVIS_PYTHON="$ROOT/jarvis/.venv/bin/python"
if [[ ! -x "$JARVIS_PYTHON" ]]; then
  echo "Run Setup_Jarvis.command first."
  read "REPLY?Press Return to close..."
  exit 1
fi
"$JARVIS_PYTHON" "$ROOT/jarvis/launch.py" --voice
read "REPLY?Press Return to close..."
