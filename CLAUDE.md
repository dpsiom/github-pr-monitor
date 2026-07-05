# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask web app for monitoring and actioning GitHub pull requests (approve, request changes, comment, merge, close) across multiple repositories. Runs in Docker or natively with Python 3.11+.

## Commands

```bash
# Setup
pip install -e .[dev]
cp config.example.yaml config.yaml
cp .env.example .env
git config core.hooksPath .githooks   # blocks direct commit/push to main

# Quality gates — all four must pass before a PR (same as CI)
ruff check src tests
mypy src --strict
pytest --cov=src --cov-report=term-missing   # coverage target: 96%+
bandit -r src

# Run a single test
pytest tests/unit/test_pr_service.py -k test_name

# Run the app (http://localhost:5000; env vars: HOST, PORT, FLASK_DEBUG)
python -m src.main

# Run via Docker
docker compose -f docker/docker-compose.yaml up
```

Never commit to `main` — the `.githooks` hooks reject it. Work on a feature branch and open a PR; CI (`ci.yaml`) runs the four quality gates plus actionlint and a workflow policy check that requires every `uses:` in `.github/workflows/` to be pinned to a version tag (e.g. `@v7.0.0`).

## Architecture

Layered design (see `docs/adr/0001-architecture.md`, but note it predates the migration from Tkinter to Flask — `src/ui` no longer exists; the "UI" layer is now `src/web`):

- **`src/web/app.py`** — Flask app factory (`create_app`). All routes are JSON APIs plus a single page at `/`. The entire frontend is one self-contained template, `src/web/templates/index.html` (inline JS/CSS, no build step, no static assets).
- **`src/services/`** — business logic:
  - `pr_service.py` (`PRService`) — owns the polling loop and dispatches PR actions to the gateway.
  - `auth_service.py` (`AuthService`) — resolves tokens for the three auth modes and validates scopes.
  - `webhook_service.py` (`WebhookService`) — optional aiohttp listener for realtime mode (`monitor.realtime_mode: webhook`).
  - `notification_service.py` — minimal in-process pub/sub (observer pattern); services publish events (`prs_updated`, `polling_error`), the web layer subscribes and caches results.
- **`src/api/github_client.py`** (`GitHubRepositoryGateway`) — the only place that talks to GitHub. Uses three client styles deliberately: GraphQL via aiohttp for the PR list (one query per repo, batched with `asyncio.gather`), REST via aiohttp for PR details (files/comments), and PyGithub wrapped in `asyncio.to_thread` for write actions (approve/merge/close). Retries use `@with_exponential_backoff` from `src/utils/rate_limiter.py`.
- **`src/config/settings.py`** — Pydantic models. `AppSettings.load()` reads `.env`, then `config.yaml`, then overlays `runtime_config.yaml`.

### Threading/async model

Flask routes are synchronous. `PRService.start()` runs the asyncio polling loop inside a daemon thread (`asyncio.run`). Routes trigger `force_refresh()` on separate background threads; a non-blocking lock makes concurrent refreshes no-ops rather than queueing. There is no shared event loop — each entry point calls `asyncio.run` itself.

### State

Fetched PRs live only in an in-memory `state` dict inside `create_app` (updated via pub/sub callbacks). There is no database. Restarting the app loses nothing except the current PR snapshot, which repopulates on the next poll.

### Two-layer configuration (important)

- `config.yaml` — repositories and monitor settings. Mounted **read-only** in Docker; the `POST /api/settings` route deliberately rejects everything except auth fields.
- `runtime_config.yaml` (at `$DATA_DIR`, default `.`) — auth settings written by the web UI (`save_auth_config()`), overlaid on top of `config.yaml` at load. Malformed runtime config is silently ignored so startup never crashes.

### Authentication modes

`auth_mode` is one of `pat`, `github_app`, `browser` (default). PAT and browser-device-flow tokens are stored via `src/utils/keychain.py`, which no-ops gracefully when no OS keyring backend exists (e.g. in Docker — token stays in memory only). GitHub App mode builds an RS256 JWT and exchanges it for an installation token on each startup. `main.py` starts the web UI even when auth fails so users can authenticate from the Settings panel.

## Conventions

- mypy runs `--strict`; type hints are required on all public functions.
- Ruff enforces `BLE` (blind except): broad `except Exception` handlers at API/route boundaries carry `# noqa: BLE001` — follow the existing pattern rather than removing them.
- Line length 100 (ruff and black).
- Tests live in `tests/unit/` (mirroring `src/` module names); `tests/integration/` and `tests/e2e/` are empty placeholders.
- For auth/API changes, note security implications in the PR description; include screenshots for UI changes.
