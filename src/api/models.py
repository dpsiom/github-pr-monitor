"""Data models for GitHub pull requests."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CIStatus(BaseModel):
    """CI check summary for a PR."""

    state: str
    total: int = 0
    passing: int = 0
    failing: int = 0
    pending: int = 0


class CheckRun(BaseModel):
    """Individual CI check run."""

    name: str
    status: str
    conclusion: str | None = None
    url: str | None = None


class PRFileSummary(BaseModel):
    """Changed files summary."""

    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class PRFileChange(BaseModel):
    """Detailed changed file metadata for a pull request."""

    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    patch: str = ""


class PRReviewComment(BaseModel):
    """Review thread comment item."""

    author: str
    body: str
    path: str | None = None
    line: int | None = None
    created_at: datetime | None = None


class PullRequest(BaseModel):
    """View model for PR display."""

    repo: str
    number: int
    title: str
    author: str
    body: str = ""
    state: str
    is_draft: bool = False
    base_branch: str
    head_branch: str
    labels: list[str] = Field(default_factory=list)
    milestone: str | None = None
    reviewers: list[str] = Field(default_factory=list)
    review_comments_count: int = 0
    html_url: str
    updated_at: datetime
    files: PRFileSummary = Field(default_factory=PRFileSummary)
    ci_status: CIStatus = Field(default_factory=lambda: CIStatus(state="UNKNOWN"))
    checks: list[CheckRun] = Field(default_factory=list)
    file_changes: list[PRFileChange] = Field(default_factory=list)
    review_comments: list[PRReviewComment] = Field(default_factory=list)
