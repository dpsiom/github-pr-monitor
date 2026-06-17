"""GitHub API abstraction layer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
from github import Github
from github.PullRequest import PullRequest as PyGithubPullRequest

from src.api.models import (
    CheckRun,
    CIStatus,
    PRFileChange,
    PRFileSummary,
    PRReviewComment,
    PullRequest,
)
from src.config.settings import AppSettings
from src.utils.rate_limiter import with_exponential_backoff


@dataclass(slots=True)
class GitHubRepositoryGateway:
    """Repository pattern adapter for GitHub APIs."""

    settings: AppSettings
    token: str

    @property
    def _rest_api_url(self) -> str:
        """Return REST API base URL."""
        return self.settings.api_base_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-pr-monitor",
        }

    async def fetch_pending_review_prs(self, repositories: list[str]) -> list[PullRequest]:
        """Fetch open pull requests requiring review from configured repos."""
        tasks = [self._fetch_repo_prs(repo) for repo in repositories]
        nested = await asyncio.gather(*tasks, return_exceptions=False)
        flat = [item for sub in nested for item in sub]
        flat.sort(key=lambda pr: pr.updated_at, reverse=True)
        return flat

    async def fetch_pull_request_details(self, pr: PullRequest) -> PullRequest:
        """Fetch review comments and changed files for a PR."""
        owner, name = pr.repo.split("/", maxsplit=1)
        files_url = f"{self._rest_api_url}/repos/{owner}/{name}/pulls/{pr.number}/files"
        comments_url = f"{self._rest_api_url}/repos/{owner}/{name}/pulls/{pr.number}/comments"

        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(files_url, ssl=True, params={"per_page": 100}) as files_response:
                files_response.raise_for_status()
                files_payload: list[dict[str, Any]] = await files_response.json()
            async with session.get(
                comments_url, ssl=True, params={"per_page": 100}
            ) as comments_response:
                comments_response.raise_for_status()
                comments_payload: list[dict[str, Any]] = await comments_response.json()

        pr.file_changes = [
            PRFileChange(
                path=item.get("filename", ""),
                status=item.get("status", "unknown"),
                additions=item.get("additions", 0),
                deletions=item.get("deletions", 0),
                patch=item.get("patch", "") or "",
            )
            for item in files_payload
        ]
        pr.review_comments = [
            PRReviewComment(
                author=(item.get("user") or {}).get("login", "unknown"),
                body=item.get("body", ""),
                path=item.get("path"),
                line=item.get("line"),
                created_at=(
                    datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                    if item.get("created_at")
                    else None
                ),
            )
            for item in comments_payload
        ]
        return pr

    @with_exponential_backoff()
    async def _fetch_repo_prs(self, repository: str) -> list[PullRequest]:
        """Fetch PRs for one repository using GraphQL."""
        owner, name = repository.split("/", maxsplit=1)
        query = """
        query($owner:String!, $name:String!) {
          repository(owner:$owner, name:$name) {
            pullRequests(states: OPEN, first: 30, orderBy: {field: UPDATED_AT, direction: DESC}) {
              nodes {
                number
                title
                body
                isDraft
                state
                url
                updatedAt
                author { login }
                baseRefName
                headRefName
                reviewThreads(first: 1) { totalCount }
                labels(first: 10) { nodes { name } }
                milestone { title }
                reviewRequests(first: 20) { nodes { requestedReviewer { ... on User { login } } } }
                files(first: 1) {
                  totalCount
                  nodes {
                    additions
                    deletions
                  }
                }
                commits(last: 1) {
                  nodes {
                    commit {
                      statusCheckRollup {
                        state
                        contexts(first: 50) {
                          nodes {
                            ... on CheckRun {
                              __typename
                              name
                              status
                              conclusion
                              detailsUrl
                            }
                            ... on StatusContext {
                              __typename
                              context
                              state
                              targetUrl
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"owner": owner, "name": name}
        payload = {"query": query, "variables": variables}

        async with (
            aiohttp.ClientSession(headers=self._headers) as session,
            session.post(self.settings.graphql_url, json=payload, ssl=True) as response,
        ):
            response.raise_for_status()
            body: dict[str, Any] = await response.json()

        nodes = body.get("data", {}).get("repository", {}).get("pullRequests", {}).get("nodes", [])
        parsed: list[PullRequest] = []
        for node in nodes:
            reviewers = [
                req["requestedReviewer"]["login"]
                for req in node.get("reviewRequests", {}).get("nodes", [])
                if req.get("requestedReviewer") and req["requestedReviewer"].get("login")
            ]
            file_node = (node.get("files", {}).get("nodes", []) or [{}])[0]
            commit_node = (
                node.get("commits", {})
                .get("nodes", [{}])[0]
                .get("commit", {})
            )
            rollup = commit_node.get("statusCheckRollup") or {}
            ci_state = rollup.get("state", "UNKNOWN")

            checks: list[CheckRun] = []
            for ctx in (rollup.get("contexts", {}).get("nodes", []) or []):
                typename = ctx.get("__typename", "")
                if typename == "CheckRun":
                    checks.append(CheckRun(
                        name=ctx.get("name", ""),
                        status=ctx.get("status", ""),
                        conclusion=ctx.get("conclusion"),
                        url=ctx.get("detailsUrl"),
                    ))
                elif typename == "StatusContext":
                    checks.append(CheckRun(
                        name=ctx.get("context", ""),
                        status=ctx.get("state", ""),
                        conclusion=ctx.get("state"),
                        url=ctx.get("targetUrl"),
                    ))

            parsed.append(
                PullRequest(
                    repo=repository,
                    number=node["number"],
                    title=node["title"],
                    author=(node.get("author") or {}).get("login", "unknown"),
                    body=node.get("body") or "",
                    state=node["state"],
                    is_draft=node.get("isDraft", False),
                    base_branch=node.get("baseRefName", ""),
                    head_branch=node.get("headRefName", ""),
                    labels=[label["name"] for label in node.get("labels", {}).get("nodes", [])],
                    milestone=(node.get("milestone") or {}).get("title"),
                    reviewers=reviewers,
                    review_comments_count=node.get("reviewThreads", {}).get("totalCount", 0),
                    html_url=node.get("url", ""),
                    updated_at=datetime.fromisoformat(node["updatedAt"].replace("Z", "+00:00")),
                    files=PRFileSummary(
                        additions=file_node.get("additions", 0),
                        deletions=file_node.get("deletions", 0),
                        changed_files=node.get("files", {}).get("totalCount", 0),
                    ),
                    ci_status=CIStatus(state=ci_state),
                    checks=checks,
                )
            )

        return parsed

    async def approve(self, repository: str, number: int, comment: str | None = None) -> None:
        """Approve a pull request."""
        await asyncio.to_thread(self._create_review, repository, number, "APPROVE", comment)

    async def request_changes(self, repository: str, number: int, comment: str) -> None:
        """Request changes on a pull request."""
        await asyncio.to_thread(self._create_review, repository, number, "REQUEST_CHANGES", comment)

    async def comment(self, repository: str, number: int, comment: str) -> None:
        """Add a comment to a pull request."""
        await asyncio.to_thread(self._create_review, repository, number, "COMMENT", comment)

    async def add_line_comment(
        self,
        repository: str,
        number: int,
        body: str,
        path: str,
        line: int,
    ) -> None:
        """Create a line-level review comment on a pull request."""
        owner, name = repository.split("/", maxsplit=1)
        payload = {
            "body": body,
            "path": path,
            "line": line,
            "side": "RIGHT",
        }
        async with (
            aiohttp.ClientSession(headers=self._headers) as session,
            session.post(
                f"{self._rest_api_url}/repos/{owner}/{name}/pulls/{number}/comments",
                json=payload,
                ssl=True,
            ) as response,
        ):
            response.raise_for_status()

    async def merge(self, repository: str, number: int, method: str = "merge") -> None:
        """Merge a pull request using selected strategy."""
        await asyncio.to_thread(self._merge_pr, repository, number, method)

    async def close(self, repository: str, number: int) -> None:
        """Close a pull request."""
        await asyncio.to_thread(self._close_pr, repository, number, None)

    async def close_with_comment(self, repository: str, number: int, comment: str | None) -> None:
        """Close a pull request and optionally add a final comment."""
        await asyncio.to_thread(self._close_pr, repository, number, comment)

    def _create_review(self, repository: str, number: int, event: str, comment: str | None) -> None:
        gh = Github(self.token)
        repo = gh.get_repo(repository)
        pr: PyGithubPullRequest = repo.get_pull(number)
        if comment:
            pr.create_review(event=event, body=comment)
            return
        pr.create_review(event=event)

    def _merge_pr(self, repository: str, number: int, method: str) -> None:
        gh = Github(self.token)
        repo = gh.get_repo(repository)
        pr = repo.get_pull(number)
        pr.merge(merge_method=method)

    def _close_pr(self, repository: str, number: int, comment: str | None) -> None:
        gh = Github(self.token)
        repo = gh.get_repo(repository)
        pr: PyGithubPullRequest = repo.get_pull(number)
        if comment:
            pr.create_issue_comment(comment)
        pr.edit(state="closed")
