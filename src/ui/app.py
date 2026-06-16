"""Main desktop application window."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from src.api.models import PullRequest
from src.config.settings import AppConfig, AppSettings
from src.services.pr_service import PRService
from src.ui.views.pr_detail_view import PRDetailView
from src.ui.views.pr_list_view import PRListView
from src.ui.views.settings_view import SettingsDialog


class PRMonitorApp:
    """Tkinter app shell and view orchestration."""

    def __init__(self, settings: AppSettings, pr_service: PRService) -> None:
        self.settings = settings
        self.pr_service = pr_service
        self.prs: list[PullRequest] = []
        self.last_updated: datetime | None = None

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk()
        self.root.title("GitHub PR Monitor")
        self.root.geometry("1200x760")

        self.status_var = tk.StringVar(value="Starting...")

        self._build_layout()
        self.pr_service.subscribe_updates(self._on_prs_updated)
        self.pr_service.subscribe_error(self._on_polling_error)
        self.pr_service.notification_service.subscribe(
            "connection_status", self._on_connection_status
        )
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        toolbar = ctk.CTkFrame(self.root)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 0))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(toolbar, text="Settings", command=self._open_settings).grid(
            row=0,
            column=1,
            padx=4,
            pady=4,
        )

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(1, weight=1)

        self.list_view = PRListView(self.root, on_select=self._on_pr_selected)
        self.list_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        self.detail_view = PRDetailView(self.root, on_action=self._on_action)
        self.detail_view.grid(row=1, column=1, sticky="nsew", padx=12, pady=12)

        status = ctk.CTkLabel(self.root, textvariable=self.status_var, anchor="w")
        status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

    def run(self) -> None:
        """Start services and run mainloop."""
        self.pr_service.start()
        self.root.mainloop()

    def _on_prs_updated(self, prs: list[PullRequest], ts: datetime) -> None:
        self.prs = prs
        self.last_updated = ts
        self.root.after(0, self._refresh_ui)

    def _refresh_ui(self) -> None:
        self.list_view.set_items(self.prs)
        timestamp = self.last_updated.strftime("%Y-%m-%d %H:%M:%S") if self.last_updated else "n/a"
        self.status_var.set(f"Connected | Last updated: {timestamp}")

    def _on_polling_error(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(f"Offline/Error: {message}"))

    def _on_pr_selected(self, pr: PullRequest) -> None:
        self.detail_view.set_pr(pr)
        self.status_var.set("Loading PR details...")

        def worker() -> None:
            try:
                detailed = self.pr_service.get_pull_request_details(pr)
                self.root.after(0, lambda: self.detail_view.set_pr(detailed))
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)
                self.root.after(
                    0,
                    lambda: self.status_var.set(f"Detail load failed: {error_message}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_action(
        self,
        action: str,
        pr: PullRequest,
        comment: str | None,
        merge_method: str,
        line_path: str | None,
        line_number: int | None,
    ) -> None:
        def worker() -> None:
            try:
                self.pr_service.run_action(
                    action=action,
                    pr=pr,
                    comment=comment,
                    merge_method=merge_method,
                    line_path=line_path,
                    line_number=line_number,
                )
                self.root.after(
                    0,
                    lambda: messagebox.showinfo("Success", f"Action '{action}' completed"),
                )
                self.pr_service.force_refresh()
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Action Failed", error_message),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self) -> None:
        self.pr_service.stop()
        self.root.destroy()

    def _on_connection_status(self, _event: str, payload: str) -> None:
        """Render realtime connection updates into status line."""
        self.root.after(0, lambda: self.status_var.set(payload))

    def _open_settings(self) -> None:
        """Open settings dialog for monitored repository configuration."""
        SettingsDialog(
            self.root,
            initial_config=self.settings.config,
            on_save=self._save_settings,
        )

    def _save_settings(self, config: AppConfig) -> None:
        """Persist new settings and restart monitor services."""
        self.settings.config = config
        self.settings.save_config()
        self.pr_service.stop()
        self.pr_service = PRService(settings=self.settings, token=self.pr_service.gateway.token)
        self.pr_service.subscribe_updates(self._on_prs_updated)
        self.pr_service.subscribe_error(self._on_polling_error)
        self.pr_service.notification_service.subscribe(
            "connection_status", self._on_connection_status
        )
        self.pr_service.start()
        self.status_var.set("Settings saved and monitoring restarted")
