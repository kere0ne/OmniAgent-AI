# Security Policy

## Reporting a vulnerability

Open a GitHub security advisory ("Report a vulnerability" on the Security tab) or
contact the maintainers directly. Please do not open a public issue for an
unpatched vulnerability. You will get credit in the release notes unless you prefer
otherwise.

## Scope

- Sandbox escapes from the execution environment (see docs/sandbox-security.md)
- Authentication or authorization bypass between users
- Path traversal in any file endpoint
- Secret exposure through any API surface

## Hardening expectations for operators

- Set a long random `OMNI_SECRET_KEY`; never ship the default.
- Use the Docker Compose deployment for multi-user setups; the bare executor is
  process-isolated only.
- Put the app behind HTTPS; keep the database file or Postgres host private.
- API keys and GitHub tokens are stored server-side and are never returned by the API.
