#!/usr/bin/env python3
# OmniAgent AI backend entrypoint (the CloudVPS watchdog runs: python3 start.sh)
import os, re, subprocess, sys, time, urllib.request
BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
def log(m): print(m, flush=True)
if not os.path.exists("cloudflared"):
    try:
        log("[omniagent] downloading cloudflared...")
        urllib.request.urlretrieve("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "cloudflared")
        os.chmod("cloudflared", 0o755)
        log("[omniagent] cloudflared ready")
    except Exception as e:
        log(f"[omniagent] cloudflared download failed: {e}")
if os.path.exists("cloudflared"):
    tf = open("tunnel.log", "w")
    subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate"], stdout=tf, stderr=subprocess.STDOUT)
    url = None
    for _ in range(25):
        time.sleep(1)
        try:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", open("tunnel.log").read())
            if m: url = m.group(0); break
        except Exception: pass
    if url: log(f"TUNNEL_URL: {url}")
    else: log("[omniagent] tunnel URL not found yet; check tunnel.log")
import uvicorn
log("[omniagent] starting API on :8000")
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
