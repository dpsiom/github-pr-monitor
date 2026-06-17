"""Tests for GitHub API gateway parsing and request behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.github_client import GitHubRepositoryGateway
from src.api.models import CIStatus, PRFileSummary, PullRequest
from src.config.settings import AppSettings


class DummyResponse:
    """Minimal async response context manager."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    async def __aenter__(self) -> DummyResponse:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        _ = (exc_type, exc, tb)
        return False

    def raise_for_status(self) -> None:
        return

    async def json(self) -> Any:
        return self._payload


class DummySession:
    """Minimal async ClientSession replacement."""

    def __init__(self, post_payloads: list[Any], get_payloads: list[Any]) -> None:
        self._post_payloads = post_payloads
        self._get_payloads = get_payloads
        self.post_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> DummySession:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        _ = (exc_type, exc, tb)
        return False

    def post(self, url: str, **kwargs: Any) -> DummyResponse:
        self.post_calls.append({"url": url, **kwargs})
        return DummyResponse(self._post_payloads.pop(0))

    def get(self, _url: str, **_kwargs: Any) -> DummyResponse:
        return DummyResponse(self._get_payloads.pop(0))


@pytest.mark.asyncio
async def test_fetch_pending_review_prs_parses_graphql() -> None:
    graphql_payload = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [
                        {
                            "number": 12,
                            "title": "Add feature",
                            "body": "Body",
                            "isDraft": False,
                            "state": "OPEN",
                            "url": "https://example/pull/12",
                            "updatedAt": "2026-06-15T15:00:00Z",
                            "author": {"login": "octocat"},
                            "baseRefName": "main",
                            "headRefName": "feat",
                            "reviewThreads": {"totalCount": 2},
                            "labels": {"nodes": [{"name": "enhancement"}]},
                            "milestone": {"title": "m1"},
                            "reviewRequests": {
                                "nodes": [{"requestedReviewer": {"login": "reviewer1"}}]
                            },
                            "files": {
                                "totalCount": 1,
                                "nodes": [{"additions": 3, "deletions": 1}],
                            },
                            "commits": {
                                "nodes": [{
                                    "commit": {
                                        "statusCheckRollup": {
                                            "state": "SUCCESS",
                                            "contexts": {
                                                "nodes": [
                                                    {
                                                        "__typename": "CheckRun",
                                                        "name": "CI / checks",
                                                        "status": "COMPLETED",
                                                        "conclusion": "SUCCESS",
                                                        "detailsUrl": "https://example/runs/1",
                                                    },
                                                    {
                                                        "__typename": "StatusContext",
                                                        "context": "deploy",
                                                        "state": "SUCCESS",
                                                        "targetUrl": "https://example/deploy",
                                                    },
                                                ]
                                            },
                                        }
                                    }
                                }]
                            },
                        }
                    ]
                }
            }
        }
    }
    session = DummySession(post_payloads=[graphql_payload], get_payloads=[])

    with patch("src.api.github_client.aiohttp.ClientSession", return_value=session):
        gateway = GitHubRepositoryGateway(settings=AppSettings(), token="token")
        prs = await gateway.fetch_pending_review_prs(["octo/repo"])

    assert len(prs) == 1
    assert prs[0].number == 12
    assert prs[0].author == "octocat"
    assert prs[0].labels == ["enhancement"]
    assert len(prs[0].checks) == 2
    assert prs[0].checks[0].name == "CI / checks"
    assert prs[0].checks[0].conclusion == "SUCCESS"
    assert prs[0].checks[1].name == "deploy"


@pytest.mark.asyncio
async def test_fetch_pull_request_details_populates_changes_and_comments() -> None:
    files_payload = [
        {
            "filename": "src/main.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "patch": "@@ -1 +1 @@",
        }
    ]
    comments_payload = [
        {
            "user": {"login": "reviewer1"},
            "body": "Please rename this",
            "path": "src/main.py",
            "line": 10,
            "created_at": "2026-06-15T15:00:00Z",
        }
    ]
    issue_comments_payload = [
        {
            "user": {"login": "copilot[bot]", "type": "Bot"},
            "body": "Automated review suggestion",
            "author_association": "NONE",
            "created_at": "2026-06-15T16:00:00Z",
        },
        {
            "user": {"login": "octocat", "type": "User"},
            "body": "Thanks for the review",
            "author_association": "MEMBER",
            "created_at": "2026-06-15T17:00:00Z",
        },
    ]
    session = DummySession(
        post_payloads=[],
        get_payloads=[files_payload, comments_payload, issue_comments_payload],
    )

    with patch("src.api.github_client.aiohttp.ClientSession", return_value=session):
        gateway = GitHubRepositoryGateway(settings=AppSettings(), token="token")
        pr = PullRequest(
            repo="octo/repo",
            number=1,
            title="Title",
            author="octocat",
            state="OPEN",
            base_branch="main",
            head_branch="feat",
            html_url="https://example",
            updated_at=datetime.now(),
            files=PRFileSummary(),
            ci_status=CIStatus(state="SUCCESS"),
        )
        detailed = await gateway.fetch_pull_request_details(pr)

    assert detailed.file_changes[0].path == "src/main.py"
    assert detailed.review_comments[0].author == "reviewer1"
    assert len(detailed.comments) == 2
    assert detailed.comments[0].author == "copilot[bot]"
    assert detailed.comments[0].is_bot is True
    assert detailed.comments[1].author == "octocat"
    assert detailed.comments[1].is_bot is False


@pytest.mark.asyncio
async def test_add_line_comment_posts_to_rest_endpoint() -> None:
    session = DummySession(post_payloads=[{}], get_payloads=[])

    with patch("src.api.github_client.aiohttp.ClientSession", return_value=session):
        gateway = GitHubRepositoryGateway(settings=AppSettings(), token="token")
        await gateway.add_line_comment(
            repository="octo/repo",
            number=42,
            body="nit",
            path="src/main.py",
            line=15,
        )

    assert len(session.post_calls) == 1
    payload = session.post_calls[0]["json"]
    assert payload["path"] == "src/main.py"
    assert payload["line"] == 15


@pytest.mark.asyncio
async def test_async_wrappers_use_to_thread() -> None:
    gateway = GitHubRepositoryGateway(settings=AppSettings(), token="token")

    with patch("src.api.github_client.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        await gateway.approve("octo/repo", 1, "ok")
        await gateway.request_changes("octo/repo", 1, "fix")
        await gateway.comment("octo/repo", 1, "note")
        await gateway.merge("octo/repo", 1, "squash")
        await gateway.close("octo/repo", 1)
        await gateway.close_with_comment("octo/repo", 1, "closing")

    assert mock_to_thread.await_count == 6


@patch("src.api.github_client.Github")
def test_sync_helpers_call_pygithub(mock_github_cls: Mock) -> None:
    repo = Mock()
    pr = Mock()
    repo.get_pull.return_value = pr
    gh = Mock()
    gh.get_repo.return_value = repo
    mock_github_cls.return_value = gh

    gateway = GitHubRepositoryGateway(settings=AppSettings(), token="token")
    gateway._create_review("octo/repo", 2, "COMMENT", "body")  # noqa: SLF001
    gateway._create_review("octo/repo", 2, "APPROVE", None)  # noqa: SLF001
    gateway._merge_pr("octo/repo", 2, "merge")  # noqa: SLF001
    gateway._close_pr("octo/repo", 2, "done")  # noqa: SLF001

    assert pr.create_review.call_count == 2
    pr.merge.assert_called_once_with(merge_method="merge")
    pr.create_issue_comment.assert_called_once_with("done")
    pr.edit.assert_called_once_with(state="closed")
