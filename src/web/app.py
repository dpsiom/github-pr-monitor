"""Flask web application for GitHub PR Monitor."""

from __future__ import annotations

import os
import threading
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.api.models import PullRequest
from src.config.settings import AppSettings
from src.services.pr_service import PRService


def create_app(settings: AppSettings, pr_service: PRService) -> Flask:
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
                "auth_mode": config.auth_mode,
            }
        )

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
    return base
