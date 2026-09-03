#!/bin/zsh
set -e

ROOT="${0:A:h}"

if command -v python3.12 >/dev/null; then
  PYTHON="$(command -v python3.12)"
elif command -v python3 >/dev/null; then
  PYTHON="$(command -v python3)"
else
  echo "Python 3.11 or later is required."
  read "REPLY?Press Return to close..."
  exit 1
fi

if command -v brew >/dev/null && ! brew list portaudio >/dev/null 2>&1; then
  echo "Installing the microphone audio component..."
  brew install portaudio
fi

echo "Setting up the router..."
"$PYTHON" -m venv "$ROOT/router/.venv"
"$ROOT/router/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/router/.venv/bin/python" -m pip install -r "$ROOT/router/requirements.txt"

echo "Setting up the desktop assistant..."
"$PYTHON" -m venv "$ROOT/jarvis/.venv"
"$ROOT/jarvis/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/jarvis/.venv/bin/python" -m pip install -r "$ROOT/jarvis/requirements.txt"

if [[ ! -f "$ROOT/router/.env" ]]; then
  cp "$ROOT/router/.env.example" "$ROOT/router/.env"
  echo
  echo "Setup created router/.env. Add your Groq key and a random router secret there."
fi

echo
echo "Setup finished. Configure router/.env, then double-click Start_Jarvis.command."
read "REPLY?Press Return to close..."
