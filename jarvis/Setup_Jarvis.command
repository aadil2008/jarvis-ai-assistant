#!/bin/zsh
set -e
cd "${0:A:h}"

if command -v python3.12 >/dev/null; then
  PYTHON="$(command -v python3.12)"
elif command -v python3 >/dev/null; then
  PYTHON="$(command -v python3)"
else
  echo "Python 3 is required. Install it from python.org, then run this setup again."
  read "REPLY?Press Return to close..."
  exit 1
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)'; then
  echo "Local speech setup requires Python 3.11-3.13. Install Python 3.12 from python.org and retry."
  read "REPLY?Press Return to close..."
  exit 1
fi

if command -v brew >/dev/null && ! brew list portaudio >/dev/null 2>&1; then
  echo "Installing the microphone audio component..."
  brew install portaudio
fi

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo
.venv/bin/python setup_assistant.py || { read "REPLY?Press Return to close..."; exit 1; }
echo "Double-click Start_Jarvis.command after setup succeeds."
read "REPLY?Press Return to close..."
