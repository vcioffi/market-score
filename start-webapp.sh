#!/usr/bin/env bash
# Start the Market Score React webapp (Vite dev server)
set -e

WEBAPP_DIR="$(cd "$(dirname "$0")/webapp" && pwd)"
cd "$WEBAPP_DIR"

# Install dependencies if node_modules is missing
if [ ! -d "node_modules" ]; then
  echo "▶ Installing npm dependencies..."
  npm install
fi

echo "▶ Starting webapp on http://localhost:5173"
npm run dev
