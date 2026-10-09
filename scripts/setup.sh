#!/usr/bin/env bash
# OmniAgent AI development setup: installs backend deps, builds the frontend, runs tests.
set -e
cd "$(dirname "$0")/.."
python3 -m pip install -r backend/requirements.txt
if ! command -v node >/dev/null; then
  echo "Node.js 20+ required for the frontend build: https://nodejs.org"
  exit 1
fi
cd frontend && npm install --no-audit --no-fund && npm run build
cd ../backend && python3 -m pytest tests/ -q
echo
echo "Setup complete. Start the app with:  cd backend && uvicorn app.main:app --port 8000"
