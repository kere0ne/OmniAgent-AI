#!/bin/bash
# OmniAgent AI backend launcher: installs deps, starts API, exposes a Cloudflare quick tunnel.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv || python3 -m pip install --user virtualenv; fi
if [ -d .venv ]; then PIP=.venv/bin/pip; PY=.venv/bin/python; else PIP="python3 -m pip install --user"; PY=python3; fi
$PIP install -q -r requirements.txt || python3 -m pip install -q -r requirements.txt
if [ ! -f cloudflared ]; then
  curl -fsSL -o cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x cloudflared
fi
if [ -f cloudflared ]; then
  nohup ./cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate > tunnel.log 2>&1 &
fi
exec $PY -m uvicorn app.main:app --host 0.0.0.0 --port 8000
