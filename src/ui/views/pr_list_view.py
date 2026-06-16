"""PR list pane."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from src.api.models import PullRequest


class PRListView(ctk.CTkFrame):  # type: ignore[misc]
    """Displays monitored PRs."""

    def __init__(self, master: ctk.CTk, on_select: Callable[[PullRequest], None]) -> None:
        super().__init__(master)
        self.on_select = on_select
        self.items: list[PullRequest] = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="Pending Reviews", font=("Helvetica", 20, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        self.listbox = ctk.CTkTextbox(self, wrap="word")
        self.listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.listbox.bind("<Button-1>", self._handle_click)

    def set_items(self, prs: list[PullRequest]) -> None:
        self.items = prs
        self.listbox.configure(state="normal")
        self.listbox.delete("1.0", "end")
        for index, pr in enumerate(prs, start=1):
            line = f"{index:02d}. [{pr.repo}] #{pr.number} {pr.title} ({pr.author})\n"
            self.listbox.insert("end", line)
        self.listbox.configure(state="disabled")

    def _handle_click(self, event: object) -> None:
        index = int(float(self.listbox.index("current").split(".")[0])) - 1
        if 0 <= index < len(self.items):
            self.on_select(self.items[index])
