# Sandbox security

## What the executor enforces

Every command (agent tool, terminal session, exec endpoint) runs as a child process with:

- **Resource limits** (`setrlimit`): CPU time (default 120s), address space (768MB),
  file size (256MB), process count (128), core dumps disabled. Configurable via env.
- **Scrubbed environment**: only PATH, HOME (set to the workspace), TERM, LANG and
  explicitly passed variables. Server secrets are never present.
- **Working directory jail**: commands run with cwd inside the workspace; file tools
  resolve every path and reject anything that escapes the workspace root.
- **Blocked binaries**: sudo, su, mount, umount, ssh, scp, iptables, nsenter are refused
  (exit 126) before execution.
- **Timeouts**: wall-clock timeout per command (default 60s, hard max 600s); the whole
  process group is killed on expiry.
- **Quotas**: per-workspace disk quota (default 500MB) enforced before writes and uploads.
- **Audit logs**: every exec, upload, clone, commit, and push is recorded with user and detail.

## What it does not enforce (and how to get it)

The default executor is a process-level sandbox on a shared kernel. It is appropriate
for single-user or trusted-group deployments. It is NOT a security boundary against a
determined malicious user on a multi-tenant host. For that:

- Run the backend in the provided Docker Compose stack (container boundary, read-only
  app image, non-root user).
- For untrusted multi-tenant workloads, run each workspace in its own container (gVisor,
  Firecracker, or a plain Docker container per workspace). `executor.run()` is the single
  choke point: swap its subprocess call for a container runtime call to isolate per workspace.
- Restrict outbound network at the host/container firewall level if agent commands must
  not reach the internet.

## Untrusted input

- Uploaded ZIPs are extracted with per-entry path validation (zip-slip rejected with a 400).
- Repository content is treated as untrusted data, never as instructions to the platform.
- Tool inputs are validated against JSON schemas; tool permissions are enforced per user
  (`allow`/`deny` lists) before any tool executes.

## Secrets

- Provider API keys and GitHub tokens are stored server-side (DB) and never returned by
  any API response (only a `has_api_key`/`has_token` boolean).
- GitHub push injects the token into the remote URL in memory only and masks it in output.
- Terminal WebSockets authenticate with the same signed session token as REST endpoints.
