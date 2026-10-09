# Troubleshooting

**"No AI model configured"** when chatting or running an agent: add a provider on the
Models page. Ollama is the free/local path (see docs/models.md).

**Provider test fails with "connection failed"**: the backend can't reach the base URL.
For local Ollama check `ollama serve` is running (`curl localhost:11434/api/tags`). If
OmniAgent runs in Docker, use `http://host.docker.internal:11434/v1` (add
`extra_hosts: host.docker.internal:host-gateway` on Linux) instead of localhost.

**Agent finishes instantly with "Reached the step limit"**: the model isn't calling
tools. Some models need larger `max_tokens`; others don't support tool calling at all.
Use a tool-calling-capable model (qwen2.5-coder, llama3.1+ work with Ollama).

**Terminal says "unknown or expired session"**: sessions die with the server process.
Open a new terminal tab session.

**Upload rejected with 413/507**: file exceeds `OMNI_UPLOAD_MAX_MB` or the workspace
disk quota (`OMNI_WORKSPACE_QUOTA_MB`).

**Exec returns exit 126 "blocked"**: the command uses a prohibited binary (sudo, ssh, ...).
Run it on your own machine instead; the sandbox deliberately refuses it.

**Port 8000 busy**: `uvicorn app.main:app --port 8001` (then open http://localhost:8001).

**Forgot admin/reset**: users are equal (no admin yet); delete the SQLite file to start
fresh, or manage users directly in the DB.
