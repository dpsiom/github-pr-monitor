# GitHub PR Monitor

A modern web application for monitoring and actioning GitHub pull requests across multiple repositories — approve, review, comment, merge, and close from your browser.

Runs as a lightweight Flask app in Docker. Open **[http://localhost:5000](http://localhost:5000)** and you're done.

---

## Quick start — Docker Compose

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 2. Create your `config.yaml`

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to list your repositories and select browser auth:

```yaml
repositories:
  - name: your-org/your-repo       # owner/repo format
    enabled: true
  - name: your-org/another-repo
    enabled: true

monitor:
  poll_interval_seconds: 60        # minimum 30
  realtime_mode: polling           # or: webhook

auth_mode: browser

browser_auth:
  enabled: true
  client_id: Iv1.your_oauth_app_client_id
  scopes: repo read:org
```

### 3. Pull and run

```bash
docker compose -f docker/docker-compose.yaml up
```

The full `docker/docker-compose.yaml` for reference:

```yaml
services:
  app:
    image: ghcr.io/dpsiom/github-pr-monitor:latest
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    ports:
      - "5000:5000"
```

### 4. Open the app

Open **[http://localhost:5000](http://localhost:5000)** in your browser.
Open the settings icon, choose **Browser Sign-in (OAuth)**, then click **Authenticate In Browser**.

---

## Alternative: `docker run`

```bash
docker run --rm \
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
- Secure browser sign-in with GitHub OAuth device flow
- Async polling with optional realtime webhook mode
- Lightweight Flask backend — no VNC, no X11, no desktop dependencies

---

## Authentication

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
  -v /absolute/path/to/app.pem:/run/secrets/app.pem:ro \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 5000:5000 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

### Browser Sign-in (OAuth device flow)

Use this mode when you want interactive sign-in in your browser, similar to GitHub login in desktop tools. If your organization uses Okta (or another IdP) through GitHub SSO, GitHub handles that redirect automatically.

```yaml
auth_mode: browser

browser_auth:
  enabled: true
  client_id: "Iv1.your_oauth_app_client_id"
  scopes: "repo read:org"
```

Then open the app UI, click the settings icon, choose **Browser Sign-in (OAuth)**, save, and click **Authenticate In Browser**.

---

## Running natively (Python)

Requires Python 3.11+.

```bash
pip install -e .
cp config.example.yaml config.yaml   # edit as above
python -m src.main
```

The web UI will be available at **http://localhost:5000**.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `docker pull` denied | Image not yet published — build locally: `docker build -f docker/Dockerfile -t github-pr-monitor .` then use `github-pr-monitor` as the image name |
| Browser "connection refused" | Wait a few seconds for the container to start, then refresh |
| Empty PR list | Check `config.yaml` repository names are `owner/repo` format and complete browser authentication from the Settings panel |
| Port 5000 in use | Use `-p 5001:5000` and open `http://localhost:5001` |
| Rate limit errors | Increase `monitor.poll_interval_seconds` (minimum 30) |
| Browser auth fails immediately | Verify `browser_auth.client_id` is a valid GitHub OAuth app client ID and `browser_auth.enabled` is true |

---

## Contributing and development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, quality gates, branch workflow, and release process.
