"""Status badge component."""

from __future__ import annotations

import customtkinter as ctk


class StatusBadge(ctk.CTkLabel):  # type: ignore[misc]
    """Simple colored status badge."""

    COLORS = {
        "SUCCESS": "#1f8a70",
        "FAILURE": "#c0392b",
        "PENDING": "#f39c12",
        "UNKNOWN": "#7f8c8d",
    }

    def set_status(self, status: str) -> None:
        upper = status.upper()
        self.configure(
            text=upper,
            fg_color=self.COLORS.get(upper, self.COLORS["UNKNOWN"]),
            corner_radius=8,
        )
