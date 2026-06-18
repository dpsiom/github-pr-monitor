"""Tests for the Flask web application."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.api.models import (
    CheckRun,
    CIStatus,
    PRComment,
    PRFileChange,
    PRFileSummary,
    PRReviewComment,
    PullRequest,
)
from src.config.settings import AppConfig, AppSettings
from src.web.app import create_app


def _sample_pr() -> PullRequest:
    return PullRequest(
        repo="octo/repo",
        number=1,
        title="Add feature",
        author="octocat",
        state="OPEN",
        body="Some description",
        base_branch="main",
        head_branch="feat",
        html_url="https://github.com/octo/repo/pull/1",
        updated_at=datetime(2024, 1, 15, 10, 30),
        files=PRFileSummary(additions=5, deletions=2, changed_files=3),
        ci_status=CIStatus(state="SUCCESS"),
        labels=["enhancement"],
        reviewers=["reviewer1"],
        checks=[
            CheckRun(name="CI / checks", status="COMPLETED", conclusion="SUCCESS", url="https://github.com/runs/1"),
            CheckRun(name="CI / build", status="COMPLETED", conclusion="FAILURE", url="https://github.com/runs/2"),
        ],
        file_changes=[
            PRFileChange(
                path="src/main.py", status="modified", additions=3, deletions=1, patch="+a\n-b"
            )
        ],
        review_comments=[
            PRReviewComment(author="reviewer1", body="Looks good", path="src/main.py", line=10)
        ],
        comments=[
            PRComment(
                author="copilot[bot]",
                body="Automated suggestion",
                author_association="NONE",
                is_bot=True,
            ),
            PRComment(
                author="octocat",
                body="Thanks!",
                author_association="MEMBER",
                is_bot=False,
            ),
        ],
    )


@pytest.fixture
def client():
    settings = AppSettings(config=AppConfig())
    pr_service = Mock()
    auth_service = Mock()
    auth_service.authenticate_browser_session = Mock(return_value="browser-token")
    auth_service.validate_token_scopes = Mock()
    pr_service.subscribe_updates = Mock()
    pr_service.subscribe_error = Mock()
    pr_service.get_pull_request_details = Mock(return_value=_sample_pr())
    pr_service.run_action = Mock()
    pr_service.force_refresh = Mock()
    pr_service.update_token = Mock()

    app = create_app(settings=settings, pr_service=pr_service, auth_service=auth_service)
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        # Simulate PR data arrival
        update_callback = pr_service.subscribe_updates.call_args[0][0]
        update_callback([_sample_pr()], datetime(2024, 1, 15, 10, 30))
        yield test_client, pr_service, auth_service, settings


def test_index_returns_html(client):
    test_client, _, _, _ = client
    response = test_client.get("/")
    assert response.status_code == 200
    assert b"PR Monitor" in response.data


def test_api_prs_returns_pr_list(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/prs")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["prs"]) == 1
    assert data["prs"][0]["title"] == "Add feature"
    assert data["prs"][0]["repo"] == "octo/repo"
    assert data["prs"][0]["ci_status"] == "SUCCESS"


def test_api_pr_detail(client):
    test_client, pr_service, _, _ = client
    response = test_client.get("/api/prs/octo/repo/1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Add feature"
    assert len(data["file_changes"]) == 1
    assert data["file_changes"][0]["path"] == "src/main.py"
    assert len(data["review_comments"]) == 1
    assert len(data["checks"]) == 2
    assert data["checks"][0]["name"] == "CI / checks"
    assert data["checks"][0]["conclusion"] == "SUCCESS"
    assert data["checks"][1]["conclusion"] == "FAILURE"
    assert len(data["comments"]) == 2
    assert data["comments"][0]["author"] == "copilot[bot]"
    assert data["comments"][0]["is_bot"] is True
    assert data["comments"][1]["author"] == "octocat"
    pr_service.get_pull_request_details.assert_called_once()


def test_api_pr_detail_not_found(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/prs/unknown/repo/999")
    assert response.status_code == 404


def test_api_pr_action_approve(client):
    test_client, pr_service, _, _ = client
    response = test_client.post(
        "/api/prs/octo/repo/1/action",
        json={"action": "approve", "comment": "LGTM"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    pr_service.run_action.assert_called_once()
    call_kwargs = pr_service.run_action.call_args[1]
    assert call_kwargs["action"] == "approve"
    assert call_kwargs["comment"] == "LGTM"


def test_api_pr_action_missing_action(client):
    test_client, _, _, _ = client
    response = test_client.post("/api/prs/octo/repo/1/action", json={})
    assert response.status_code == 400


def test_api_pr_action_error(client):
    test_client, pr_service, _, _ = client
    pr_service.run_action.side_effect = RuntimeError("merge conflict")
    response = test_client.post(
        "/api/prs/octo/repo/1/action",
        json={"action": "merge"},
    )
    assert response.status_code == 500
    assert "merge conflict" in response.get_json()["error"]


def test_api_refresh(client):
    test_client, pr_service, _, _ = client
    response = test_client.post("/api/refresh")
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_api_settings(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/settings")
    assert response.status_code == 200
    data = response.get_json()
    assert "repositories" in data
    assert "poll_interval_seconds" in data
    assert "browser_auth" in data


def test_api_settings_save(client):
    test_client, _, _, settings = client
    response = test_client.post(
        "/api/settings",
        json={
            "repositories": [{"name": "octo/repo", "enabled": True}],
            "organization_monitoring": False,
            "organization": None,
            "monitor": {
                "poll_interval_seconds": 60,
                "realtime_mode": "polling",
                "smee_url": None,
                "webhook_host": "127.0.0.1",
                "webhook_port": 8765,
                "webhook_secret": None,
            },
            "auth_mode": "browser",
            "github_app": {
                "enabled": False,
                "app_id": None,
                "installation_id": None,
                "private_key_path": None,
            },
            "browser_auth": {
                "enabled": True,
                "client_id": "Iv1.example",
                "scopes": "repo read:org",
            },
        },
    )
    assert response.status_code == 200
    assert settings.config.auth_mode == "browser"
    assert settings.config.browser_auth.client_id == "Iv1.example"


def test_api_auth_browser_start(client):
    test_client, pr_service, auth_service, _ = client
    response = test_client.post("/api/auth/browser/start")
    assert response.status_code == 200
    auth_service.authenticate_browser_session.assert_called_once_with(open_browser=True)
    auth_service.validate_token_scopes.assert_called_once_with("browser-token")
    pr_service.update_token.assert_called_once_with("browser-token")


def test_no_ansi_in_patch_response(client):
    """Ensure patch data doesn't contain ANSI escape sequences."""
    test_client, _, _, _ = client
    response = test_client.get("/api/prs/octo/repo/1")
    data = response.get_json()
    for fc in data["file_changes"]:
        assert "\x1b[" not in fc["patch"]
