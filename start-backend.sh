#!/usr/bin/env bash
# Start the Market Score FastAPI backend
set -e

BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
cd "$BACKEND_DIR"

# Activate virtualenv if present
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
fi

HOST="${MARKET_SCORE_HOST:-0.0.0.0}"
PORT="${MARKET_SCORE_PORT:-8000}"
RELOAD="${MARKET_SCORE_RELOAD:-}"

echo "▶ Starting backend on http://${HOST}:${PORT}"
ARGS="--host $HOST --port $PORT"
[ -n "$RELOAD" ] && ARGS="$ARGS --reload"

python scripts/run_api.py $ARGS
