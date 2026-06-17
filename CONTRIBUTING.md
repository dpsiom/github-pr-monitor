# Contributing

## Development setup

1. Install Python 3.11+.
2. Create and activate a virtual environment.
3. Install all dependencies including dev tools:

```bash
pip install -e .[dev]
```

1. Copy example config files:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

1. Enable repository hooks to block direct commit/push to main:

```bash
git config core.hooksPath .githooks
```

## Quality gates

Run all checks before creating a PR:

```bash
ruff check src tests            # lint
mypy src --strict               # type checking
pytest --cov=src --cov-report=term-missing   # tests + coverage
bandit -r src                   # security scan
```

All four must pass. Current coverage target: **96%+**.

## Branch and PR workflow

1. Create a feature branch - never commit directly to `main`:

```bash
git checkout -b feat/my-change
```

1. Push and open a PR:

```bash
git push -u origin feat/my-change
gh pr create --base main
```

1. CI must pass before merging.

## Code standards

- Type hints required on all public functions.
- Tests required for all new logic.
- Note security implications in PR description for auth/API changes.
- Include screenshots in PR description for UI changes.

## CI workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yaml` | PR to main | Lint, type check, tests, security scan |
| `build.yaml` | Manual (`workflow_dispatch`) + PR to main | Cross-platform PyInstaller build (macOS, Linux, Windows) |
| `docker.yaml` | PR + push to main | Build Docker image; push to GHCR on merge |
| `publish.yaml` | Manual (`workflow_dispatch`) | Tag a version and publish GitHub Release |

## Publishing a release

Run the **Publish Release** workflow manually from the GitHub Actions tab.
Enter the version (with or without `v` prefix, e.g. `1.2.0` or `v1.2.0`).
The workflow will:

- Create and push the git tag
- Build cross-platform binaries
- Create a GitHub Release with checksums

## Dependency updates

Dependabot is configured (`.github/dependabot.yml`) to open weekly PRs for:

- pip package updates
- GitHub Actions version updates

## Verifying a release asset checksum

```bash
shasum -a 256 -c SHA256SUMS-Linux.txt
```
