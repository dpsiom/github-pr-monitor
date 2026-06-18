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

Edit `config.yaml` to list your repositories. **No auth config is needed here** — authentication is configured from the web UI.

```yaml
repositories:
  - name: your-org/your-repo       # owner/repo format
    enabled: true
  - name: your-org/another-repo
    enabled: true

monitor:
  poll_interval_seconds: 60        # minimum 30
  realtime_mode: polling           # or: webhook
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
    environment:
      - DATA_DIR=/app/data
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - app_data:/app/data
    ports:
      - "5000:5000"

volumes:
  app_data:
```

### 4. Configure authentication and open the app

1. Open **[http://localhost:<host_port>](http://localhost:<host_port>)** in your browser.
2. Click the **⚙ settings icon** in the top-right corner.
3. Select **Browser Sign-in (OAuth)** as the authentication type.
4. Enter your OAuth app client ID (see [Authentication](#browser-sign-in-oauth-device-flow) below for how to create one).
5. Click **Save settings**, then **Authenticate In Browser**.
6. Sign in on GitHub — if your organisation uses Okta or another SSO provider, GitHub redirects there automatically.

Authentication settings are saved to a named Docker volume (`app_data`) and persist across container restarts.

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

### Browser Sign-in (OAuth device flow) {#browser-sign-in-oauth-device-flow}

Use this mode when you want interactive sign-in in your browser, similar to GitHub login in desktop tools. If your organisation uses Okta (or another IdP) through GitHub SSO, GitHub handles that redirect automatically — no Okta-specific config required here.

**How to get a client ID:**
1. Go to **GitHub Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Set *Home page URL* to `http://localhost:<host_port>` (or your host).
3. Set *Authorization callback URL* to `http://localhost:<host_port>` (or your host).
4. Copy the **Client ID** and enter it in the app settings panel.

Authentication settings are stored in the writable `app_data` Docker volume (`/app/data/runtime_config.yaml`), not in `config.yaml`.

---

## Running natively (Python)

Requires Python 3.11+.

```bash
pip install -e .
cp config.example.yaml config.yaml   # edit as above
python -m src.main
```

The web UI will be available at **http://localhost:<host_port>**.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `docker pull` denied | Image not yet published — build locally: `docker build -f docker/Dockerfile -t github-pr-monitor .` then use `github-pr-monitor` as the image name |
| Browser "connection refused" | Wait a few seconds for the container to start, then refresh |
| Empty PR list | Check `config.yaml` repository names are `owner/repo` format and complete browser authentication from the Settings panel |
| Auth settings lost after restart | Ensure the `app_data` Docker volume is mounted (`DATA_DIR=/app/data`); auth settings are written to that volume |
| Browser auth fails immediately | Verify the OAuth client ID entered in Settings is valid |
| Port 5000 in use | Use `-p 5004:5000` and open `http://localhost:5004` |
| Rate limit errors | Increase `monitor.poll_interval_seconds` (minimum 30) |

---

## Contributing and development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, quality gates, branch workflow, and release process.
