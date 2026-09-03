#!/bin/zsh
set -e

ROOT="${0:A:h}"
ROUTER_ENV="$ROOT/router/.env"
ROUTER_PYTHON="$ROOT/router/.venv/bin/python"
JARVIS_PYTHON="$ROOT/jarvis/.venv/bin/python"
ROUTER_LOG="/tmp/jarvis-router-${UID}.log"

cd "$ROOT"

if [[ ! -x "$ROUTER_PYTHON" || ! -x "$JARVIS_PYTHON" ]]; then
  echo "Run Setup_Jarvis.command first."
  read "REPLY?Press Return to close..."
  exit 1
fi

if [[ ! -f "$ROUTER_ENV" ]]; then
  echo "router/.env is missing. Run Setup_Jarvis.command first."
  read "REPLY?Press Return to close..."
  exit 1
fi

ROUTER_KEY="$($ROUTER_PYTHON -c 'from dotenv import dotenv_values; print(dotenv_values("router/.env").get("ROUTER_API_KEY") or "")' 2>/dev/null)"
if [[ -z "$ROUTER_KEY" || "$ROUTER_KEY" == replace_with_* ]]; then
  echo "Add a private ROUTER_API_KEY to router/.env before starting JARVIS."
  read "REPLY?Press Return to close..."
  exit 1
fi

if ! "$ROUTER_PYTHON" -c 'from dotenv import dotenv_values; import sys; value = dotenv_values("router/.env").get("GROQ_API_KEY") or ""; sys.exit(0 if value.startswith("gsk_") and "your_" not in value else 1)'; then
  echo "Add your GROQ_API_KEY to router/.env before starting JARVIS."
  read "REPLY?Press Return to close..."
  exit 1
fi

cd "$ROOT/router"
"$ROUTER_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$ROUTER_LOG" 2>&1 &
ROUTER_PID=$!
trap 'kill "$ROUTER_PID" 2>/dev/null || true' EXIT INT TERM

for attempt in {1..30}; do
  if curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$ROUTER_PID" 2>/dev/null; then
    echo "The router could not start. Details are in $ROUTER_LOG"
    read "REPLY?Press Return to close..."
    exit 1
  fi
  sleep 0.2
done

if ! curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "The router did not become ready. Details are in $ROUTER_LOG"
  read "REPLY?Press Return to close..."
  exit 1
fi

cd "$ROOT/jarvis"
JARVIS_ROUTER_URL="http://127.0.0.1:8000" \
JARVIS_ROUTER_API_KEY="$ROUTER_KEY" \
"$JARVIS_PYTHON" main.py --voice

echo
read "REPLY?Press Return to close..."
