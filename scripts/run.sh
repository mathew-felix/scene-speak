#!/usr/bin/env bash
# Starts the SceneSpeak backend and launches the app in the iOS Simulator.
# Press Ctrl+C to stop both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -x /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"

[[ -x server/.venv/bin/python && -d node_modules ]] || { echo "Run ./scripts/setup.sh first."; exit 1; }

if curl -s -m 2 http://localhost:8787/health >/dev/null 2>&1; then
  echo "A server is already running on port 8787; stopping it first."
  pkill -f "uvicorn app:app" || true; pkill -f "llama-server -m" || true; sleep 3
fi

mkdir -p server/outputs
echo "Starting backend (log: server/outputs/server.log) ..."
(cd server && exec .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8787) > server/outputs/server.log 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; sleep 1; pkill -f "llama-server -m" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

for _ in $(seq 1 40); do
  curl -s -m 2 http://localhost:8787/health >/dev/null 2>&1 && break
  kill -0 "$SERVER_PID" 2>/dev/null || { echo "Backend crashed:"; tail -20 server/outputs/server.log; exit 1; }
  sleep 1
done
curl -s -m 2 http://localhost:8787/health >/dev/null 2>&1 || { echo "Backend did not start:"; tail -20 server/outputs/server.log; exit 1; }
echo "Backend ready at http://localhost:8787"

echo "Building and launching the app in the iOS Simulator (first build takes several minutes) ..."
npx expo run:ios
echo
echo "App launched. Backend is still running; press Ctrl+C here to stop it."
wait "$SERVER_PID"
