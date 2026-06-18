# GitHub PR Monitor

A modern web application for monitoring and actioning GitHub pull requests across multiple repositories — approve, review, comment, merge, and close from your browser.

Runs as a lightweight Flask app in Docker. Open **[http://localhost:5000](http://localhost:5000)** and you're done.

---

## Quick start — Docker Compose

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- A GitHub Personal Access Token ([create one here](https://github.com/settings/tokens/new?scopes=repo&description=github-pr-monitor))

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` — only `GITHUB_TOKEN` is required for PAT auth:

```dotenv
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Only needed when using GitHub App auth instead of a PAT:
GITHUB_APP_ID=
GITHUB_APP_INSTALLATION_ID=
GITHUB_APP_PRIVATE_KEY_PATH=
```

### 3. Create your `config.yaml`

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to list your repositories:

```yaml
repositories:
  - name: your-org/your-repo       # owner/repo format
    enabled: true
  - name: your-org/another-repo
    enabled: true

monitor:
  poll_interval_seconds: 60        # minimum 30
  realtime_mode: polling           # or: webhook

auth_mode: pat                     # or: github_app
```

### 4. Pull and run

```bash
docker compose -f docker/docker-compose.yaml up
```

The full `docker/docker-compose.yaml` for reference:

```yaml
services:
  app:
    image: ghcr.io/dpsiom/github-pr-monitor:latest
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_APP_ID=${GITHUB_APP_ID:-}
      - GITHUB_APP_INSTALLATION_ID=${GITHUB_APP_INSTALLATION_ID:-}
      - GITHUB_APP_PRIVATE_KEY_PATH=${GITHUB_APP_PRIVATE_KEY_PATH:-}
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    ports:
      - "5000:5000"
```

### 5. Open the app

Open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## Alternative: `docker run`

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 5000:5000 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

---

## Features

- Modern dark-themed web UI with real-time polling
- Monitor PRs across multiple repositories from one dashboard
- Actions: **approve**, **request changes**, **comment**, **merge**, **close**
- Collapsible diff viewer with syntax-highlighted patches
- Secure token loading: environment variable or OS keychain
- Async polling with optional realtime webhook mode
- Lightweight Flask backend — no VNC, no X11, no desktop dependencies

---

## Authentication

### PAT (default)

Set `GITHUB_TOKEN` in `.env`.

For a **classic PAT**, use `repo` scope. Add `read:org` if your repositories are in an organisation with restricted visibility.

For a **fine-grained PAT**, you must configure both repository access and individual permissions:

1. **Repository access** — select "Only select repositories" and add every repo listed in your `config.yaml`. Alternatively choose "All repositories" if you want blanket access, but scoped access is recommended.

2. **Repository permissions** — enable each of these:

| Permission | Access level | Why it's needed |
| --- | --- | --- |
| **Pull requests** | Read and write | List open PRs, submit reviews (approve / request changes), post comments, close PRs |
| **Contents** | Read and write | Merge pull requests (merge, squash, rebase) |
| **Commit statuses** | Read-only | View legacy commit status (CI pass/fail) for each PR |
| **Metadata** | Read-only | Required for all API access (granted automatically when any other permission is enabled) |

> **Note:** If you only need to _monitor_ PRs without taking actions, **Pull requests: Read-only**, **Commit statuses: Read-only**, and **Metadata: Read-only** are sufficient. Merge and review actions require write access.

> **⚠️ CI status on private repos:** Fine-grained PATs cannot access GitHub's Checks API (a [documented limitation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens-limitations)). If your private repo uses GitHub Actions for CI, the check run status will show as **UNKNOWN** regardless of the permissions you grant. To see CI status on private repos, use a **classic PAT** with `repo` scope, or switch to a **GitHub App** (see below).

### GitHub App

```yaml
# config.yaml
auth_mode: github_app

github_app:
  enabled: true
  app_id: "12345"
  installation_id: "67890"
  private_key_path: "/run/secrets/app.pem"
```

Mount the PEM key when running:

```bash
docker run --rm \
  -e GITHUB_APP_ID=12345 \
  -e GITHUB_APP_INSTALLATION_ID=67890 \
  -e GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/app.pem \
  -v /absolute/path/to/app.pem:/run/secrets/app.pem:ro \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 5000:5000 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

---

## Running natively (Python)

Requires Python 3.11+.

```bash
pip install -e .
cp config.example.yaml config.yaml   # edit as above
cp .env.example .env                  # set GITHUB_TOKEN
python -m src.main
```

The web UI will be available at **http://localhost:5000**.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `docker pull` denied | Image not yet published — build locally: `docker build -f docker/Dockerfile -t github-pr-monitor .` then use `github-pr-monitor` as the image name |
| Browser "connection refused" | Wait a few seconds for the container to start, then refresh |
| Empty PR list | Check `config.yaml` repository names are `owner/repo` format and token has access |
| `GITHUB_TOKEN` invalid | Ensure token has `repo` scope (classic) or correct fine-grained permissions and hasn't expired |
| Port 5000 in use | Use `-p 5001:5000` and open `http://localhost:5001` |
| Rate limit errors | Increase `monitor.poll_interval_seconds` (minimum 30) |
| CI status shows **UNKNOWN** on private repos | Fine-grained PATs cannot access the Checks API — switch to a classic PAT with `repo` scope or a GitHub App |

---

## Contributing and development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, quality gates, branch workflow, and release process.
