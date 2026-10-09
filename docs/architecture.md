# Architecture

## Overview

OmniAgent AI is a single-origin web app: a FastAPI backend that serves both the REST/WebSocket
API and the built React frontend, with a pluggable model-provider layer and a sandboxed
execution engine.

```
Browser (React + Monaco + xterm)
   |  REST + SSE + WebSocket
FastAPI backend
   |-- auth (PBKDF2 + HMAC-signed tokens, rate limiting)
   |-- routers: projects/files, terminal, chat, agents, models, git, preview
   |-- services:
   |     executor.py    sandboxed command runner (rlimits, scrubbed env, timeouts)
   |     agent.py       autonomous loop, roles, approval gating, checkpoints
   |     tools.py       tool registry (schema, permission class, structured output)
   |     providers.py   model abstraction (Ollama / OpenAI-compatible / mock)
   |     workspaces.py  path validation, quotas, safe ZIP extraction
   |-- SQLAlchemy models (SQLite by default, PostgreSQL via OMNI_DATABASE_URL)
Data dir (~/.omniagent/data or OMNI_DATA_DIR)
   |-- app.db (or external Postgres)
   |-- workspaces/u<user>/ws<workspace>/   per-user per-workspace filesystem
```

## Request flows

**Chat**: browser posts to `/api/chat/stream`; the backend loads the conversation,
prepends a system prompt (with workspace file listing when attached), streams
Server-Sent Events from the provider, and persists the final assistant message.

**Agent run**: POST `/api/agents/run` creates an AgentTask row and starts a background
thread. Each loop step: build messages (system role prompt + goal + workspace listing),
call the model with tool definitions, execute tool calls (gating mutating ones on
approval when enabled), append structured events to the task's `steps` JSON ledger
(checkpoint), and continue until `finish`, a plain final answer, the step limit,
cancellation, or failure. Approval pauses the task in `awaiting_approval`; the UI
shows the exact tool call and arguments.

**Terminal**: opening a session spawns one long-lived `bash` with piped stdio under
resource limits; a WebSocket forwards typed commands and streams output. cwd and
exported env persist across commands. PTY-based TUIs are not supported.

**Preview**: `/api/workspaces/{id}/preview/start` launches the dev server inside the
workspace; `GET /api/workspaces/{id}/preview/{path}` proxies requests to it from
authenticated sessions only. No ports are exposed publicly.

## Database

SQLite by default (zero-config local runs). Set `OMNI_DATABASE_URL` to a PostgreSQL
URL for production; the same SQLAlchemy models apply. Large project files live on the
filesystem under the data dir, not in DB rows. Migrations: schema is created via
`Base.metadata.create_all`; for evolving deployments use Alembic (tracked as a pending
improvement below).

## Limitations

- **Execution isolation**: the default executor is process-isolated (CPU/memory/file-size/
  process limits, scrubbed environment, blocked system binaries) but shares the host
  kernel with the API server. For hard isolation in multi-user deployments run the
  backend inside the provided Docker Compose stack; a per-workspace container backend is
  a documented extension point (executor.py's `run()` signature is container-ready).
- **No PTY**: interactive TUI programs (vim, htop) don't work in the terminal.
- **Alembic migrations**: not yet; schema bootstrap is create_all.
- **Multi-agent concurrency**: roles run sequentially by design to prevent file
  write conflicts; parallel read-only fan-out is a future extension.
- **GitHub PR creation**: commits and pushes are implemented; PR creation via the API
  is a planned addition.
- **Background agent threads** are in-process; a queue worker (Redis/RQ) is the
  production path for horizontal scaling.
