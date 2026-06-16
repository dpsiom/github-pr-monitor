# GitHub PR Monitor

A desktop GUI for monitoring and actioning GitHub pull requests across multiple repositories — approve, review, comment, merge, and close without leaving the app.

The GUI runs in a browser tab via Docker — **no XQuartz, no X11, nothing extra to install on macOS**.

---

## Quickest start — Docker Compose

### 1. Prerequisites

- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- A GitHub Personal Access Token with **`repo`** scope ([create one here](https://github.com/settings/tokens/new?scopes=repo&description=github-pr-monitor))

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
docker pull ghcr.io/dpsiom/github-pr-monitor:latest

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
      # Uncomment if using GitHub App auth:
      # - /absolute/path/to/app.pem:/run/secrets/app.pem:ro
    ports:
      - "6080:6080"
```

### 5. Open the app

Open **[http://localhost:6080/vnc.html?autoconnect=true&resize=scale](http://localhost:6080/vnc.html?autoconnect=true&resize=scale)** in Safari or Chrome.

---

## Alternative: `docker run`

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 6080:6080 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

---

## How the GUI works in Docker

```
Docker container
  └─ Xvfb (virtual framebuffer)
       └─ x11vnc (VNC server, localhost only)
            └─ noVNC / websockify  →  port 6080
                        │
                        ▼
              http://localhost:6080/vnc.html
              (Safari / Chrome on your Mac)
```

---

## Features

- Monitor PRs across multiple repositories from one view
- Actions: **approve**, **request changes**, **comment**, **merge**, **close**, **line-level comments**
- Secure token loading: environment variable → keychain → first-run prompt
- Async polling with optional realtime webhook mode
- In-app settings editor — no file editing required after initial setup

---

## Authentication

### PAT (default)

Set `GITHUB_TOKEN` in `.env`. Token needs `repo` scope; add `read:org` for organisation repositories.

### GitHub App

```yaml
# config.yaml
auth_mode: github_app

github_app:
  enabled: true
  app_id: "12345"
  installation_id: "67890"
  private_key_path: "/run/secrets/app.pem"   # path inside the container
```

Mount the PEM key when running:

```bash
docker run --rm \
  -e GITHUB_APP_ID=12345 \
  -e GITHUB_APP_INSTALLATION_ID=67890 \
  -e GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/app.pem \
  -v /absolute/path/to/app.pem:/run/secrets/app.pem:ro \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 6080:6080 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

---

## Running natively (Python)

Requires Python 3.11+, Tk, and a local display.

```bash
pip install -e .
cp config.example.yaml config.yaml   # edit as above
cp .env.example .env                  # set GITHUB_TOKEN
python -m src.main
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker pull` denied | Image not yet published — build locally: `docker build -f docker/Dockerfile -t github-pr-monitor .` then use `github-pr-monitor` as the image name |
| Browser "connection refused" | Wait ~5 s for the container to start, then refresh |
| Blank / black browser window | Reload — the app may still be initialising |
| Empty PR list | Check `config.yaml` repository names are `owner/repo` format and token has access |
| `GITHUB_TOKEN` invalid | Ensure token has `repo` scope and hasn't expired |
| Port 6080 in use | Use `-p 6081:6080` and open `http://localhost:6081/vnc.html` |
| Rate limit errors | Increase `monitor.poll_interval_seconds` (minimum 30) |

---

## Screenshots

Add screenshots under `docs/images/` and reference them here.

---

## Contributing and development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, quality gates, branch workflow, and release process.
