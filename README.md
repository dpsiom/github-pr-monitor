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

### GitHub App (recommended for corporate use) {#github-app}

A GitHub App is the most secure and governance-friendly authentication method. Access is restricted to specific repositories of your choosing, tokens are short-lived, and permissions are set per-action rather than granted at a broad user or organisation level.

#### Step 1 — Create the GitHub App

1. In GitHub, go to **Settings → Developer settings → GitHub Apps → New GitHub App**.
   - If you want the app scoped to your organisation (rather than your personal account), go to **Your org → Settings → Developer settings → GitHub Apps** instead.

2. Fill in the registration form:

   | Field | What to enter |
   | --- | --- |
   | **GitHub App name** | Any unique name, e.g. `pr-monitor-yourname` |
   | **Homepage URL** | `http://localhost:5000` (or any placeholder) |
   | **Webhook** | Uncheck **Active** — webhooks are not needed for polling mode |
   | **Callback URL** | Leave blank |

3. Under **Repository permissions**, set **only** the permissions below and leave everything else as **No access**:

   | Permission | Level | Why |
   | --- | --- | --- |
   | Pull requests | Read & write | Fetch, approve, comment, merge, close PRs |
   | Contents | Read-only | Read file diffs |
   | Metadata | Read-only | Required by GitHub for all apps |
   | Commit statuses | Read-only | Show commit-level CI status |

  > If your GitHub App UI shows a **Checks** permission, set it to **Read-only** to improve CI details. Some orgs/UI variants do not expose this permission; in that case, continue with the permissions above.

4. Under **Where can this GitHub App be installed?**, select **Only on this account**. This prevents anyone else installing the app.

5. Click **Create GitHub App**.

#### Step 2 — Note your App ID

After creation, stay on the app settings page. You will see:

> App ID: `123456`

Copy that number — it is your `app_id` in `config.yaml`.

#### Step 3 — Generate a private key

Still on the app settings page, scroll to the bottom and click **Generate a private key**. A `.pem` file downloads automatically to your machine. Keep it safe — it acts as the app's password.

#### Step 4 — Install the app on specific repositories

1. On the app settings page, click **Install App** in the left sidebar.
2. Click **Install** next to your account or organisation.
3. Select **Only select repositories** and choose the exact repositories you want this monitor to access.
4. Click **Install**.

After installation, GitHub takes you to the installation settings page. The URL will look like:

```
https://github.com/settings/installations/12345678
```

That number (`12345678`) is your `installation_id`.

Alternative way to find it: open the app's **Install App** page and click the configured installation; the same numeric ID appears in the URL.

#### Step 5 — Configure `config.yaml`

Edit your `config.yaml` to use GitHub App authentication. This file is mounted read-only into the container — it is the right place for these static credentials.

```yaml
# config.yaml
auth_mode: github_app

github_app:
  enabled: true
  app_id: "123456"               # from Step 2
  installation_id: "12345678"    # from Step 4
  private_key_path: "/run/secrets/app.pem"   # path inside the container

repositories:
  - name: your-org/repo-one
    enabled: true
  - name: your-org/repo-two
    enabled: true

monitor:
  poll_interval_seconds: 60
  realtime_mode: polling
```

> `client_secret` is **not required** for this app's GitHub App flow. Authentication uses `app_id` + `installation_id` + private key (`.pem`).

> Only repos that are both listed in `repositories` **and** covered by the app installation are accessible. The app cannot see anything else even if you add it to the list.

#### Step 6 — Mount the private key and run

With Docker Compose (recommended):

```yaml
# docker/docker-compose.yaml
services:
  app:
    image: ghcr.io/dpsiom/github-pr-monitor:latest
    environment:
      - DATA_DIR=/app/data
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - /absolute/path/to/your-app.pem:/run/secrets/app.pem:ro
      - app_data:/app/data
    ports:
      - "5000:5000"

volumes:
  app_data:
```

Or with `docker run`:

```bash
docker run --rm \
  -v "$PWD/config.yaml:/app/config.yaml:ro" \
  -v "/absolute/path/to/your-app.pem:/run/secrets/app.pem:ro" \
  -p 5000:5000 \
  ghcr.io/dpsiom/github-pr-monitor:latest
```

#### Restricting to a single user

A GitHub App authenticates as the app itself (not as a GitHub user). To ensure only you can operate this instance:

- Keep the `.pem` private key file on your machine only — do not commit it to any repository.
- Select **Only on this account** during registration (Step 1) so no other GitHub user can install it.
- Install on **Only select repositories** (Step 4) so the token cannot reach any other repo even if the config is modified.
- If running on a shared machine, restrict filesystem access to the `config.yaml` and `.pem` file to your user: `chmod 600 config.yaml your-app.pem`.

---

### Browser Sign-in (OAuth device flow) {#browser-sign-in-oauth-device-flow}

Use this mode when you want interactive sign-in in your browser, similar to GitHub login in desktop tools. If your organisation uses Okta (or another IdP) through GitHub SSO, GitHub handles that redirect automatically — no Okta-specific config required here.

**How to get a client ID:**
1. Go to **GitHub Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Set *Home page URL* to `http://localhost:<host_port>` (or your host).
3. Set *Authorization callback URL* to `http://localhost:<host_port>` (or your host).
4. Copy the **Client ID** and enter it in the app settings panel.

Authentication settings are stored in the writable `app_data` Docker volume (`/app/data/runtime_config.yaml`), not in `config.yaml`.

---

### Personal Access Token — fine-grained (PAT) {#pat}

A fine-grained PAT is the lightest-weight option. It is tied to your personal GitHub account and can be scoped to individual repositories. It does not require creating a GitHub App but provides less auditability and no automatic token rotation.

> **Corporate note:** Some organisations disable fine-grained PATs or require admin approval. Check with your GitHub org owner before using this method.

#### Step 1 — Create the fine-grained PAT

1. Go to **GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Fill in the token form:

   | Field | What to enter |
   | --- | --- |
   | **Token name** | Any descriptive name, e.g. `pr-monitor-local` |
   | **Expiration** | Choose the shortest period acceptable to you (90 days maximum is a sensible default) |
   | **Resource owner** | Your personal account, or your organisation if the repos are there |

3. Under **Repository access**, select **Only select repositories** and tick each repository you want the monitor to access.

4. Under **Permissions → Repository permissions**, set **only** the permissions below and leave everything else as **No access**:

   | Permission | Level | Why |
   | --- | --- | --- |
   | Pull requests | Read and write | Fetch, approve, comment, merge, close PRs |
   | Contents | Read-only | Read file diffs |
   | Commit statuses | Read-only | Show commit-level CI status |
   | Metadata | Read-only | Always required for fine-grained PATs |

  > Note: **Checks** is not a selectable permission for fine-grained PATs.

5. Click **Generate token** and copy the value immediately — GitHub will not show it again.

#### Step 2 — Enter the PAT in the app

1. Open the app at `http://localhost:5000`.
2. Click the **⚙ settings icon**.
3. Set **Authentication type** to **Personal Access Token**.
4. Paste the token into the **PAT token** field.
5. Click **Use PAT For This Session**.

The token is stored in the OS keychain (or in memory when no keychain is available, such as inside Docker). It is not written to `config.yaml`.

#### Applying the PAT to each repository

The repository-level scoping happens at token creation time (Step 1 above — **Only select repositories**). Once the token is in use, the app will only be able to call the GitHub API for those repositories regardless of what is in `config.yaml`. Any repo listed in `config.yaml` that is not covered by the token will simply return a 404 or 403 and be skipped.

#### Comparison with GitHub App

| | Fine-grained PAT | GitHub App |
| --- | --- | --- |
| Repository scope | Set at token creation | Set at app installation |
| Token lifetime | Fixed expiry (max 1 year) | Auto-rotated (1 hour) |
| Tied to a user account | Yes | No — app acts as itself |
| Requires app registration | No | Yes |
| Best for | Personal / local use | Corporate / team use |

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
| PAT — `401 Unauthorized` | The token has expired or been revoked — generate a new fine-grained PAT and re-enter it in Settings |
| PAT — `403 Forbidden` on a repo | The token was not granted access to that repository at creation time — regenerate the token with that repo included |
| GitHub App — `401 Unauthorized` | Check `app_id` and `installation_id` in `config.yaml` are correct numbers (not the app slug name) |
| GitHub App — `private_key_path` error | Ensure the `.pem` file is mounted into the container at exactly the path set in `config.yaml` and is readable |
| GitHub App — repos not shown | Confirm the app is installed on those specific repositories (GitHub → Settings → Installations) and they are listed in `config.yaml` |
| Port 5000 in use | Use `-p 5004:5000` and open `http://localhost:5004` |
| Rate limit errors | Increase `monitor.poll_interval_seconds` (minimum 30) |

---

## Contributing and development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, quality gates, branch workflow, and release process.
