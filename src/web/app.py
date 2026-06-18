"""Flask web application for GitHub PR Monitor."""

from __future__ import annotations

import os
import threading
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.api.models import PullRequest
from src.config.settings import AppConfig, AppSettings
from src.services.auth_service import AuthService
from src.services.pr_service import PRService
from src.utils.keychain import save_token_to_keychain


def create_app(settings: AppSettings, pr_service: PRService, auth_service: AuthService) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())

    # Shared state
    state: dict[str, Any] = {
        "prs": [],
        "last_updated": None,
        "error": None,
        "status": "Starting...",
    }
    auth_flow_state: dict[str, Any] = {}
    if not pr_service.gateway.token:
        state["status"] = "Authentication required — open Settings ⚙ to sign in"

    def on_prs_updated(prs: list[PullRequest], ts: datetime) -> None:
        state["prs"] = prs
        state["last_updated"] = ts
        state["error"] = None
        state["status"] = f"Connected | Last updated: {ts.strftime('%H:%M:%S')}"

    def on_error(message: str) -> None:
        state["error"] = message
        state["status"] = f"Error: {message}"

    pr_service.subscribe_updates(on_prs_updated)
    pr_service.subscribe_error(on_error)

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.route("/api/prs")
    def api_prs() -> Any:
        prs = state["prs"]
        return jsonify(
            {
                "prs": [_serialize_pr(pr) for pr in prs],
                "last_updated": (
                    state["last_updated"].isoformat() if state["last_updated"] else None
                ),
                "status": state["status"],
                "error": state["error"],
            }
        )

    @app.route("/api/prs/<path:repo>/<int:number>")
    def api_pr_detail(repo: str, number: int) -> Any:
        prs = state["prs"]
        pr = next((p for p in prs if p.repo == repo and p.number == number), None)
        if not pr:
            return jsonify({"error": "PR not found"}), 404
        try:
            detailed = pr_service.get_pull_request_details(pr)
            return jsonify(_serialize_pr_detail(detailed))
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/prs/<path:repo>/<int:number>/action", methods=["POST"])
    def api_pr_action(repo: str, number: int) -> Any:
        prs = state["prs"]
        pr = next((p for p in prs if p.repo == repo and p.number == number), None)
        if not pr:
            return jsonify({"error": "PR not found"}), 404

        data = request.get_json(force=True)
        action = data.get("action", "")
        comment = data.get("comment") or None
        merge_method = data.get("merge_method", "merge")
        line_path = data.get("line_path") or None
        line_number = data.get("line_number")

        if not action:
            return jsonify({"error": "action is required"}), 400

        try:
            pr_service.run_action(
                action=action,
                pr=pr,
                comment=comment,
                merge_method=merge_method,
                line_path=line_path,
                line_number=line_number,
            )
            # Trigger background refresh
            threading.Thread(target=pr_service.force_refresh, daemon=True).start()
            return jsonify({"success": True, "message": f"Action '{action}' completed"})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh() -> Any:
        threading.Thread(target=pr_service.force_refresh, daemon=True).start()
        return jsonify({"success": True, "message": "Refresh triggered"})

    @app.route("/api/settings")
    def api_settings() -> Any:
        config = settings.config
        return jsonify(
            {
                "repositories": [
                    {"name": r.name, "enabled": r.enabled} for r in config.repositories
                ],
                "poll_interval_seconds": config.monitor.poll_interval_seconds,
                "realtime_mode": config.monitor.realtime_mode,
                "organization_monitoring": config.organization_monitoring,
                "organization": config.organization,
                "monitor": {
                    "poll_interval_seconds": config.monitor.poll_interval_seconds,
                    "realtime_mode": config.monitor.realtime_mode,
                    "smee_url": config.monitor.smee_url,
                    "webhook_host": config.monitor.webhook_host,
                    "webhook_port": config.monitor.webhook_port,
                    "webhook_secret": config.monitor.webhook_secret,
                },
                "auth_mode": config.auth_mode,
                "github_app": {
                    "enabled": config.github_app.enabled,
                    "app_id": config.github_app.app_id,
                    "installation_id": config.github_app.installation_id,
                    "private_key_path": (
                        str(config.github_app.private_key_path)
                        if config.github_app.private_key_path
                        else None
                    ),
                },
                "browser_auth": {
                    "enabled": config.browser_auth.enabled,
                    "client_id": config.browser_auth.client_id,
                    "scopes": config.browser_auth.scopes,
                },
            }
        )

    @app.route("/api/settings", methods=["POST"])
    def api_save_settings() -> Any:
        payload = request.get_json(force=True)
        # Only auth fields are accepted; repos and monitor are read-only (config.yaml).
        auth_fields = {
            k: payload[k]
            for k in ("auth_mode", "github_app", "browser_auth")
            if k in payload
        }
        if not auth_fields:
            return jsonify({"error": "No auth fields provided"}), 400
        try:
            base = settings.config.model_dump(mode="json")
            base.update(auth_fields)
            settings.config = AppConfig.model_validate(base)
            settings.save_auth_config()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Invalid settings: {exc}"}), 400
        return jsonify({"success": True, "message": "Authentication settings saved"})

    @app.route("/api/auth/pat", methods=["POST"])
    def api_auth_pat() -> Any:
        data = request.get_json(force=True)
        token = str(data.get("token") or "").strip()
        if not token:
            return jsonify({"error": "PAT token is required"}), 400

        try:
            original_mode = settings.config.auth_mode
            settings.config.auth_mode = "pat"
            auth_service.validate_token_scopes(token)
            save_token_to_keychain(
                service_name=settings.keychain_service,
                username=settings.keychain_username,
                token=token,
            )
            pr_service.update_token(token)
            pr_service.start()
            threading.Thread(target=pr_service.force_refresh, daemon=True).start()
            return jsonify({"success": True, "message": "PAT authentication completed"})
        except Exception as exc:  # noqa: BLE001
            settings.config.auth_mode = original_mode
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/auth/browser/start", methods=["POST"])
    def api_auth_browser_start() -> Any:
        try:
            flow = auth_service.begin_browser_device_flow()
            auth_flow_state["device_code"] = flow["device_code"]
            auth_flow_state["interval"] = flow["interval"]
            auth_flow_state["expires_in"] = flow["expires_in"]
            auth_flow_state["started_at"] = datetime.now().timestamp()
            return jsonify(
                {
                    "success": True,
                    "message": "Open the browser URL and complete GitHub sign-in",
                    "verification_url": flow["verification_url"],
                    "user_code": flow["user_code"],
                    "interval": flow["interval"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/auth/browser/poll", methods=["POST"])
    def api_auth_browser_poll() -> Any:
        device_code = auth_flow_state.get("device_code")
        interval = auth_flow_state.get("interval")
        expires_in = auth_flow_state.get("expires_in")
        started_at = auth_flow_state.get("started_at")
        if not device_code or interval is None or expires_in is None or started_at is None:
            return jsonify({"error": "No active browser authentication session"}), 400

        elapsed = datetime.now().timestamp() - float(started_at)
        remaining = int(expires_in) - int(elapsed)
        if remaining <= 0:
            auth_flow_state.clear()
            return jsonify({"error": "Browser authentication session expired"}), 400

        try:
            token = auth_service.complete_browser_device_flow(
                device_code=str(device_code),
                interval=1,
                expires_in=1,
                open_browser=False,
                single_check=True,
            )
            auth_service.validate_token_scopes(token)
            pr_service.update_token(token)
            pr_service.start()
            threading.Thread(target=pr_service.force_refresh, daemon=True).start()
            auth_flow_state.clear()
            return jsonify(
                {
                    "success": True,
                    "completed": True,
                    "message": "Browser authentication completed and session updated",
                }
            )
        except PermissionError as exc:
            message = str(exc)
            if "pending" in message.lower() or "timed out" in message.lower():
                return jsonify({"success": True, "completed": False, "pending": True})
            return jsonify({"error": message}), 400

    return app


def _serialize_pr(pr: PullRequest) -> dict[str, Any]:
    """Serialize a PR to JSON-safe dict for the API."""
    return {
        "repo": pr.repo,
        "number": pr.number,
        "title": pr.title,
        "author": pr.author,
        "state": pr.state,
        "is_draft": pr.is_draft,
        "base_branch": pr.base_branch,
        "head_branch": pr.head_branch,
        "html_url": pr.html_url,
        "updated_at": pr.updated_at.isoformat(),
        "labels": pr.labels,
        "reviewers": pr.reviewers,
        "ci_status": pr.ci_status.state,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "conclusion": c.conclusion,
                "url": c.url,
            }
            for c in pr.checks
        ],
        "files": {
            "additions": pr.files.additions,
            "deletions": pr.files.deletions,
            "changed_files": pr.files.changed_files,
        },
    }


def _serialize_pr_detail(pr: PullRequest) -> dict[str, Any]:
    """Serialize detailed PR including file changes and comments."""
    base = _serialize_pr(pr)
    base["body"] = pr.body
    base["file_changes"] = [
        {
            "path": f.path,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "patch": f.patch,
        }
        for f in pr.file_changes
    ]
    base["review_comments"] = [
        {
            "author": c.author,
            "body": c.body,
            "path": c.path,
            "line": c.line,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in pr.review_comments
    ]
    base["comments"] = [
        {
            "author": c.author,
            "body": c.body,
            "author_association": c.author_association,
            "is_bot": c.is_bot,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in pr.comments
    ]
    return base
