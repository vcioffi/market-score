#!/usr/bin/env bash
# Start backend + webapp together
# Usage: ./start.sh [--reload]
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Pass --reload to backend if requested
if [[ "$*" == *"--reload"* ]]; then
  export MARKET_SCORE_RELOAD=1
fi

echo "════════════════════════════════════════"
echo "  Market Score — starting all services"
echo "  Backend : http://localhost:8000"
echo "  Webapp  : http://localhost:5173"
echo "  Stop    : Ctrl+C"
echo "════════════════════════════════════════"

# Trap Ctrl+C and kill both processes
trap 'echo; echo "Stopping..."; kill 0' SIGINT SIGTERM

bash "$ROOT/start-backend.sh" &
BACKEND_PID=$!

# Small delay so backend can bind its port before webapp starts
sleep 1

bash "$ROOT/start-webapp.sh" &
WEBAPP_PID=$!

wait $BACKEND_PID $WEBAPP_PID
