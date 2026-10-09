# Contributing

Thanks for helping make OmniAgent AI better.

1. Fork the repo and create a feature branch from `main`.
2. Keep the backend covered: add or extend `backend/tests/` for behavior changes.
3. Run `python -m pytest tests/ -q` and `npm run build` in `frontend/` before opening a PR.
4. Keep PRs focused; one feature or fix per PR.
5. Never commit real credentials, tokens, or `.env` files.

## Adding a tool

Register it in `backend/app/services/tools.py` with `register()`: a JSON schema, a
permission class (`read`, `write`, `exec`), and a function returning structured output.
Mutating tools must be listed in `MUTATING` so approval gating covers them.

## Adding a provider

Subclass the provider in `backend/app/services/providers.py` with `list_models`,
`test_connection`, and `chat`, and add the kind to the models router's validation.
