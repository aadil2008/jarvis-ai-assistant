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

if command -v brew >/dev/null && ! brew list portaudio >/dev/null 2>&1; then
  echo "Installing the microphone audio component..."
  brew install portaudio
fi

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Setup finished. Double-click Start_Jarvis.command to begin."
echo "macOS may ask for Microphone, Accessibility, and Screen Recording permission."
read "REPLY?Press Return to close..."
