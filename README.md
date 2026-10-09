# OmniAgent AI

An open-source autonomous AI software engineering platform: an AI agent with real
sandboxed execution, a browser IDE, a persistent terminal, live previews, Git/GitHub
integration, and free-first local model support (Ollama, llama.cpp, any
OpenAI-compatible endpoint).

Every feature is backed by a real backend. Commands run in an isolated execution
environment with resource limits; the agent only reports what its tool results
actually showed.

## Features

- **Autonomous agent** with a PLAN -> INSPECT -> ACT -> OBSERVE -> DEBUG -> VERIFY -> COMPLETE
  loop, structured tool calls, checkpointed event ledger, cancellation, approval gating
  for writes and commands, step limits, and bounded retries.
- **Specialized agent roles**: architect, engineer, debugger, reviewer, tester, researcher, devops, docs.
- **Real terminal**: persistent interactive shell per workspace over WebSocket, real
  stdout/stderr/exit codes, cwd and env persistence, timeouts and kill.
- **Browser IDE**: Monaco editor, file tree, tabs, create/delete, dirty tracking, save.
- **Projects & workspaces**: per-user isolation, disk quotas, uploads with ZIP extraction
  and path-traversal protection, workspace archive download.
- **Live preview**: start a dev server inside the workspace and view it through an
  authenticated proxy; nothing is exposed publicly.
- **Git & GitHub**: clone, status/log/diff/branch, commit, push with a stored fine-grained
  PAT (used in-memory only). Local git works without any GitHub setup.
- **Model abstraction**: Ollama, llama.cpp, vLLM, LM Studio, OpenAI, Groq, or any
  OpenAI-compatible endpoint. Streaming chat. Keys stay server-side, never in the browser.
- **Security**: signed session tokens, PBKDF2 password hashing, per-user workspace
  isolation, path validation on every file operation, resource-limited execution,
  rate limiting, audit logs, and an allow/deny tool-permission policy per user.
- **Open source**: MIT licensed, Docker Compose deployment, CI, tests, and docs.

## Quickstart

Requirements: Python 3.11+, Node.js 20+.

```bash
git clone https://github.com/kere0ne/OmniAgent-AI.git
cd OmniAgent-AI

# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000          # serves the API and the built frontend

# frontend (first time, or when changing frontend code)
cd ../frontend
npm install
npm run build

# open http://localhost:8000 and register an account
```

Or with Docker:

```bash
cp .env.example .env    # set a real OMNI_SECRET_KEY first
docker compose up --build
# open http://localhost:8000
```

## Run a free local model

1. Install [Ollama](https://ollama.com): `curl -fsSL https://ollama.com/install.sh | sh`
2. `ollama serve` (runs on 127.0.0.1:11434)
3. `ollama pull llama3.2` (or `qwen2.5-coder` for coding tasks)
4. In OmniAgent: Models -> Add provider -> Ollama (default address already prefilled) ->
   set model `llama3.2` -> Test -> Add.

Any OpenAI-compatible server (llama.cpp `server`, LM Studio, vLLM) works the same way.
The built-in mock provider lets you exercise the agent loop offline without any model.

## Running tests

```bash
cd backend
python -m pytest tests/ -q
```

Tests cover auth, per-user project isolation, path-traversal rejection, ZIP-slip
protection, real sandboxed command execution (stdout, exit codes, blocked binaries,
environment stripping), the agent loop against a scripted provider, and useful failures
when no model is configured.

## Documentation

- [Architecture](docs/architecture.md)
- [Sandbox security](docs/sandbox-security.md)
- [Model configuration](docs/models.md)
- [Troubleshooting](docs/troubleshooting.md)

## Known limitations

See [docs/architecture.md](docs/architecture.md#limitations). Headline items:
the default executor is process-isolated (rlimits + scrubbed env), not container-isolated;
use the provided Docker Compose setup for hard isolation in multi-user deployments.
Interactive PTY features (vim, top) are not supported in the terminal; long-running
processes run through the preview manager instead.

## License

MIT
