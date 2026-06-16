"""PR detail pane with actions."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import DiffLexer

from src.api.models import PullRequest
from src.ui.components.status_badge import StatusBadge

ActionCallback = Callable[
    [str, PullRequest, str | None, str, str | None, int | None],
    None,
]


class PRDetailView(ctk.CTkFrame):  # type: ignore[misc]
    """Displays selected PR details and action controls."""

    def __init__(self, master: ctk.CTk, on_action: ActionCallback) -> None:
        super().__init__(master)
        self.current_pr: PullRequest | None = None
        self.on_action = on_action

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        self.header = ctk.CTkLabel(self, text="Select a PR", font=("Helvetica", 20, "bold"))
        self.header.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        self.badge = StatusBadge(self, text="UNKNOWN")
        self.badge.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))

        self.meta = ctk.CTkLabel(self, text="", justify="left")
        self.meta.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))

        self.comment_input = ctk.CTkTextbox(self, height=80)
        self.comment_input.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))

        controls = ctk.CTkFrame(self)
        controls.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(2, weight=1)

        self.merge_strategy = ctk.CTkOptionMenu(
            controls,
            values=["merge", "squash", "rebase"],
        )
        self.merge_strategy.set("merge")
        self.merge_strategy.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.line_path_input = ctk.CTkEntry(
            controls,
            placeholder_text="Line comment path (e.g. src/main.py)",
        )
        self.line_path_input.grid(row=0, column=1, sticky="ew", padx=6)

        self.line_number_input = ctk.CTkEntry(
            controls,
            placeholder_text="Line number",
        )
        self.line_number_input.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        self.body = ctk.CTkTextbox(self, wrap="word")
        self.body.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 8))

        actions = ctk.CTkFrame(self)
        actions.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 10))

        for col in range(6):
            actions.grid_columnconfigure(col, weight=1)

        ctk.CTkButton(
            actions,
            text="Approve",
            command=lambda: self._trigger("approve"),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            actions,
            text="Request Changes",
            command=lambda: self._trigger("request_changes"),
        ).grid(
            row=0,
            column=1,
            padx=4,
        )
        ctk.CTkButton(
            actions,
            text="Comment",
            command=lambda: self._trigger("comment"),
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            actions,
            text="Merge",
            command=lambda: self._trigger("merge"),
        ).grid(row=0, column=3, padx=4)
        ctk.CTkButton(
            actions,
            text="Close",
            command=lambda: self._trigger("close"),
        ).grid(row=0, column=4, padx=4)
        ctk.CTkButton(
            actions,
            text="Line Comment",
            command=lambda: self._trigger("line_comment"),
        ).grid(row=0, column=5, padx=4)

    def set_pr(self, pr: PullRequest) -> None:
        self.current_pr = pr
        self.header.configure(text=f"{pr.repo} #{pr.number} - {pr.title}")
        self.badge.set_status(pr.ci_status.state)
        self.meta.configure(
            text=(
                f"Author: {pr.author} | State: {pr.state} | Draft: {pr.is_draft}\n"
                f"Branches: {pr.head_branch} -> {pr.base_branch}\n"
                f"Files: +{pr.files.additions} / -{pr.files.deletions} ({pr.files.changed_files})\n"
                f"Reviewers: {', '.join(pr.reviewers) if pr.reviewers else 'none'}\n"
                f"Labels: {', '.join(pr.labels) if pr.labels else 'none'}"
            )
        )
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("end", f"Description:\n\n{pr.body}\n\n")

        if pr.file_changes:
            self.body.insert("end", "Changed Files:\n\n")
            for item in pr.file_changes[:10]:
                self.body.insert(
                    "end",
                    (f"- {item.path} ({item.status}) +{item.additions} -{item.deletions}\n"),
                )
                if item.patch:
                    highlighted = highlight(item.patch, DiffLexer(), TerminalFormatter())
                    self.body.insert("end", f"{highlighted}\n")
        else:
            self.body.insert("end", "Changed Files: detail not loaded yet.\n\n")

        if pr.review_comments:
            self.body.insert("end", "Review Comments:\n\n")
            for comment in pr.review_comments[:20]:
                location = (
                    f"{comment.path}:{comment.line}"
                    if comment.path and comment.line is not None
                    else "general"
                )
                self.body.insert(
                    "end",
                    f"[{comment.author}] ({location}) {comment.body}\n\n",
                )
        else:
            self.body.insert("end", "Review Comments: none.\n")

        self.body.configure(state="disabled")

    def _trigger(self, action: str) -> None:
        if not self.current_pr:
            return
        comment = self.comment_input.get("1.0", "end").strip() or None
        line_path = self.line_path_input.get().strip() or None
        raw_line_number = self.line_number_input.get().strip()
        line_number = int(raw_line_number) if raw_line_number.isdigit() else None
        self.on_action(
            action,
            self.current_pr,
            comment,
            self.merge_strategy.get(),
            line_path,
            line_number,
        )
