"""Settings dialog for repository and monitoring configuration."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from src.config.settings import AppConfig

SaveCallback = Callable[[AppConfig], None]


class SettingsDialog(ctk.CTkToplevel):  # type: ignore[misc]
    """Configuration editor for repositories and runtime options."""

    def __init__(self, master: ctk.CTk, initial_config: AppConfig, on_save: SaveCallback) -> None:
        super().__init__(master)
        self.title("Monitor Settings")
        self.geometry("760x720")
        self._on_save = on_save

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Repositories (one owner/repo per line)",
            font=("Helvetica", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self.repo_box = ctk.CTkTextbox(self, height=180)
        self.repo_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.repo_box.insert(
            "1.0",
            "\n".join(repo.name for repo in initial_config.repositories if repo.enabled),
        )

        form = ctk.CTkFrame(self)
        form.grid(row=2, column=0, sticky="ew", padx=12, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Poll Interval Seconds").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        self.poll_interval = ctk.CTkEntry(form)
        self.poll_interval.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        self.poll_interval.insert(0, str(initial_config.monitor.poll_interval_seconds))

        ctk.CTkLabel(form, text="Realtime Mode").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.realtime_mode = ctk.CTkOptionMenu(form, values=["polling", "webhook"])
        self.realtime_mode.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        self.realtime_mode.set(initial_config.monitor.realtime_mode)

        ctk.CTkLabel(form, text="Smee URL").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.smee_url = ctk.CTkEntry(form)
        self.smee_url.grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.monitor.smee_url:
            self.smee_url.insert(0, initial_config.monitor.smee_url)

        ctk.CTkLabel(form, text="Webhook Host").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.webhook_host = ctk.CTkEntry(form)
        self.webhook_host.grid(row=3, column=1, sticky="ew", padx=6, pady=6)
        self.webhook_host.insert(0, initial_config.monitor.webhook_host)

        ctk.CTkLabel(form, text="Webhook Port").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        self.webhook_port = ctk.CTkEntry(form)
        self.webhook_port.grid(row=4, column=1, sticky="ew", padx=6, pady=6)
        self.webhook_port.insert(0, str(initial_config.monitor.webhook_port))

        ctk.CTkLabel(form, text="Webhook Secret").grid(row=5, column=0, sticky="w", padx=6, pady=6)
        self.webhook_secret = ctk.CTkEntry(form)
        self.webhook_secret.grid(row=5, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.monitor.webhook_secret:
            self.webhook_secret.insert(0, initial_config.monitor.webhook_secret)

        ctk.CTkLabel(form, text="Organization Monitoring").grid(
            row=6,
            column=0,
            sticky="w",
            padx=6,
            pady=6,
        )
        self.org_enabled = ctk.CTkSwitch(form, text="Enable")
        self.org_enabled.grid(row=6, column=1, sticky="w", padx=6, pady=6)
        if initial_config.organization_monitoring:
            self.org_enabled.select()

        ctk.CTkLabel(form, text="Organization Name").grid(
            row=7, column=0, sticky="w", padx=6, pady=6
        )
        self.organization_name = ctk.CTkEntry(form)
        self.organization_name.grid(row=7, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.organization:
            self.organization_name.insert(0, initial_config.organization)

        ctk.CTkLabel(form, text="Auth Mode").grid(row=8, column=0, sticky="w", padx=6, pady=6)
        self.auth_mode = ctk.CTkOptionMenu(form, values=["pat", "github_app"])
        self.auth_mode.grid(row=8, column=1, sticky="ew", padx=6, pady=6)
        self.auth_mode.set(initial_config.auth_mode)

        ctk.CTkLabel(form, text="GitHub App ID").grid(row=9, column=0, sticky="w", padx=6, pady=6)
        self.app_id = ctk.CTkEntry(form)
        self.app_id.grid(row=9, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.github_app.app_id:
            self.app_id.insert(0, initial_config.github_app.app_id)

        ctk.CTkLabel(form, text="Installation ID").grid(
            row=10, column=0, sticky="w", padx=6, pady=6
        )
        self.installation_id = ctk.CTkEntry(form)
        self.installation_id.grid(row=10, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.github_app.installation_id:
            self.installation_id.insert(0, initial_config.github_app.installation_id)

        ctk.CTkLabel(form, text="Private Key Path").grid(
            row=11, column=0, sticky="w", padx=6, pady=6
        )
        self.private_key_path = ctk.CTkEntry(form)
        self.private_key_path.grid(row=11, column=1, sticky="ew", padx=6, pady=6)
        if initial_config.github_app.private_key_path:
            self.private_key_path.insert(0, str(initial_config.github_app.private_key_path))

        actions = ctk.CTkFrame(self)
        actions.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(actions, text="Save", command=self._save).grid(
            row=0, column=0, padx=6, pady=6
        )
        ctk.CTkButton(actions, text="Cancel", command=self.destroy).grid(
            row=0, column=1, padx=6, pady=6
        )

    def _save(self) -> None:
        repositories = [
            {"name": line.strip(), "enabled": True}
            for line in self.repo_box.get("1.0", "end").splitlines()
            if line.strip()
        ]

        config = AppConfig.model_validate(
            {
                "repositories": repositories,
                "organization_monitoring": bool(self.org_enabled.get()),
                "organization": self.organization_name.get().strip() or None,
                "auth_mode": self.auth_mode.get(),
                "github_app": {
                    "enabled": self.auth_mode.get() == "github_app",
                    "app_id": self.app_id.get().strip() or None,
                    "installation_id": self.installation_id.get().strip() or None,
                    "private_key_path": self.private_key_path.get().strip() or None,
                },
                "monitor": {
                    "poll_interval_seconds": int(self.poll_interval.get()),
                    "realtime_mode": self.realtime_mode.get(),
                    "smee_url": self.smee_url.get().strip() or None,
                    "webhook_host": self.webhook_host.get().strip() or "127.0.0.1",
                    "webhook_port": int(self.webhook_port.get()),
                    "webhook_secret": self.webhook_secret.get().strip() or None,
                },
            }
        )
        self._on_save(config)
        self.destroy()
