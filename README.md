# GitHub PR Monitor

GitHub PR Monitor is a Python desktop GUI application for tracking pull requests across repositories and performing review actions from one place.

## Features (MVP)

- Secure token loading from environment variable, keychain, and first-run prompt
- Repository list driven by YAML configuration
- In-app settings editor to add/remove/edit repositories and monitor/auth mode
- Async polling monitor with observer updates into UI
- PR list and detail panes with metadata and CI state
- Actions: approve, request changes, comment, merge, close, and line-level comments
- Rate-limit retry helper with exponential backoff
- Realtime mode with local webhook listener and polling fallback

## Quick Start

1. Create and activate a Python 3.11+ environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Create local configuration files:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

4. Set token in .env or your shell:

```bash
GITHUB_TOKEN=ghp_xxx
```

5. Run app:

```bash
python -m src.main
```

## Authentication Setup

Preferred order:

1. Environment variable GITHUB_TOKEN
2. Keychain token (stored with keyring)
3. First-run prompt in app (stored to keychain)

Token must include at least repo scope.

### GitHub App Alternative

You can authenticate via GitHub App installation token.

In config.yaml:

auth_mode: github_app

github_app:
	enabled: true
	app_id: "12345"
	installation_id: "67890"
	private_key_path: "/absolute/path/to/private-key.pem"

## Configuration

Use config.yaml (gitignored) based on config.example.yaml.

repositories: list of owner/repo values.

monitor.poll_interval_seconds must be >= 30.

monitor.realtime_mode supports polling and webhook.

For webhook mode with smee.io:

1. Set monitor.realtime_mode: webhook.
2. Start relay (outside app):

```bash
npx smee-client --url https://smee.io/YOUR_CHANNEL --target http://127.0.0.1:8765/webhook
```

3. Add the smee URL in config for operator reference.

The app still runs polling fallback at your configured interval.

## Running in Docker on macOS

### How the GUI works inside Docker

GitHub PR Monitor is a native desktop application (tkinter). Inside the container a
**virtual framebuffer** (Xvfb) and a **VNC-to-browser bridge** (noVNC) are started
automatically. You access the GUI through any browser already on your Mac — **no
XQuartz, no X11, nothing extra to install**.

```
Docker container
  └─ Xvfb (virtual display :0)
       └─ x11vnc (VNC server, localhost only)
            └─ noVNC / websockify (HTTP WebSocket proxy on port 6080)
                   │
                   ▼  http://localhost:6080/vnc.html
              Safari / Chrome on your Mac  →  GUI window
```

### Prerequisites

- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) — nothing else.

### Downloading the image

Pre-built images are published to GitHub Container Registry on every tagged release:

```bash
docker pull ghcr.io/dpsiom/github-pr-monitor:latest
```

To use a specific release tag (e.g. v0.1.0):

```bash
docker pull ghcr.io/dpsiom/github-pr-monitor:v0.1.0
```

To build locally from source instead:

```bash
docker build -f docker/Dockerfile -t github-pr-monitor .
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes (PAT mode) | Personal Access Token with `repo` scope |
| `GITHUB_APP_ID` | GitHub App mode | Application ID from your GitHub App |
| `GITHUB_APP_INSTALLATION_ID` | GitHub App mode | Installation ID for the target org/user |
| `GITHUB_APP_PRIVATE_KEY_PATH` | GitHub App mode | Path **inside the container** to the PEM key file |

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
# Set GITHUB_TOKEN=ghp_xxx  (and GitHub App fields if using App auth)
```

### Running with `docker run`

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -p 6080:6080 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

Then open **http://localhost:6080/vnc.html** in Safari or Chrome.

For an auto-connecting scaled view append query parameters:

```
http://localhost:6080/vnc.html?autoconnect=true&resize=scale
```

### Running with Docker Compose

```bash
GITHUB_TOKEN=ghp_xxx docker compose -f docker/docker-compose.yaml up
```

Then open **http://localhost:6080/vnc.html** in your browser.

### Passing in a config file

Mount your local `config.yaml` read-only:

```bash
-v "$PWD/config.yaml:/app/config.yaml:ro"
```

See `config.example.yaml` for the full schema (repositories, poll interval, auth mode, webhook settings).

### Using GitHub App authentication in Docker

Mount the private key PEM into the container and point the env var at it:

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

### Troubleshooting Docker

| Symptom | Fix |
|---|---|
| Browser shows "connection refused" | Wait ~3 s for the container to fully start, then refresh |
| Blank / black browser window | Reload the page; the app may still be initialising |
| `GITHUB_TOKEN` invalid | Ensure the token has `repo` scope |
| Empty PR list | Verify `config.yaml` repository names are in `owner/repo` format |
| Port 6080 already in use | Change the host port: `-p 6081:6080` and open `http://localhost:6081/vnc.html` |

## Tooling and Quality Gates

Run checks:

```bash
pytest --cov=src --cov-report=term-missing
mypy src --strict
ruff check src tests
bandit -r src
```

## Build and Release Artifacts

- Pull requests run a cross-platform build artifact workflow to verify packaging on macOS, Linux, and Windows.
- Tagging a release with `v*` runs a cross-platform release workflow and uploads packaged binaries to the GitHub Release.
- Each release upload includes a platform checksum file (`SHA256SUMS-<OS>.txt`).
- CI enforces explicit version-tag refs for third-party GitHub Actions in workflow files.

## Dependency Automation

- Dependabot is configured in `.github/dependabot.yml` for weekly updates to pip dependencies and GitHub Actions references.

Verify a downloaded asset:

```bash
shasum -a 256 -c SHA256SUMS-Linux.txt
```

## Troubleshooting

- **Invalid token** — ensure token is active and includes `repo` scope.
- **Empty PR list** — verify repository names are in `owner/repo` format and the token has access.
- **Rate limit errors** — increase `monitor.poll_interval_seconds` (minimum 30) and retry later.
- **Keychain issues** — clear the stored keychain item and re-enter the token at the first-run prompt.
- **Docker GUI issues** — see the Docker troubleshooting table above.

## Screenshots

Add screenshots under docs/images and reference them here once captured.
