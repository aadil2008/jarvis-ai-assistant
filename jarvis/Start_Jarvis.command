#!/bin/zsh
cd "${0:A:h}"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

"$PYTHON" main.py --voice
echo
read "REPLY?Press Return to close..."
