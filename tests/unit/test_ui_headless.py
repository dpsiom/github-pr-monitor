"""Headless tests for UI modules using lightweight tkinter/customtkinter stubs."""

from __future__ import annotations

import sys
import types
from datetime import datetime

from src.api.models import CIStatus, PRFileChange, PRFileSummary, PRReviewComment, PullRequest
from src.config.settings import AppConfig, AppSettings


class _FakeWidget:
    def __init__(self, *_args: object, **kwargs: object) -> None:
        self._text = ""
        self._value = ""
        self._state = "normal"
        self._cmd = kwargs.get("command")

    def grid(self, **_kwargs: object) -> None:
        return

    def grid_columnconfigure(self, *_args: object, **_kwargs: object) -> None:
        return

    def grid_rowconfigure(self, *_args: object, **_kwargs: object) -> None:
        return

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            self._text = str(kwargs["text"])
        if "state" in kwargs:
            self._state = str(kwargs["state"])

    def bind(self, *_args: object, **_kwargs: object) -> None:
        return

    def delete(self, *_args: object, **_kwargs: object) -> None:
        self._text = ""

    def insert(self, *_args: object, **kwargs: object) -> None:
        if kwargs:
            return

    def title(self, *_args: object, **_kwargs: object) -> None:
        return

    def geometry(self, *_args: object, **_kwargs: object) -> None:
        return

    def protocol(self, *_args: object, **_kwargs: object) -> None:
        return

    def mainloop(self) -> None:
        return

    def after(self, _delay: int, callback: object) -> None:
        if callable(callback):
            callback()

    def destroy(self) -> None:
        return

    def get(self, *_args: object, **_kwargs: object) -> str:
        return self._text

    def set(self, value: str) -> None:
        self._value = value

    def index(self, _token: str) -> str:
        return "1.0"

    def select(self) -> None:
        self._value = "1"


class _FakeTextbox(_FakeWidget):
    def __init__(self, *_args: object, **kwargs: object) -> None:
        super().__init__(*_args, **kwargs)
        self._current_index = "1.0"

    def insert(self, *_args: object, **kwargs: object) -> None:
        if kwargs:
            return
        if len(_args) >= 2:
            self._text += str(_args[1])

    def get(self, *_args: object, **_kwargs: object) -> str:
        return self._text

    def index(self, _token: str) -> str:
        return self._current_index


class _FakeEntry(_FakeWidget):
    def insert(self, _idx: int | str, value: str) -> None:
        self._text = value


class _FakeOptionMenu(_FakeWidget):
    def __init__(self, *_args: object, **kwargs: object) -> None:
        super().__init__(*_args, **kwargs)
        values = kwargs.get("values")
        self._value = values[0] if values else ""

    def get(self) -> str:
        return self._value


class _FakeSwitch(_FakeWidget):
    def get(self) -> int:
        return 1 if self._value == "1" else 0


class _FakeStringVar:
    def __init__(self, value: str = "") -> None:
        self._v = value

    def set(self, value: str) -> None:
        self._v = value

    def get(self) -> str:
        return self._v


def _install_fake_gui_modules() -> None:
    ctk = types.ModuleType("customtkinter")
    ctk.CTk = _FakeWidget
    ctk.CTkFrame = _FakeWidget
    ctk.CTkLabel = _FakeWidget
    ctk.CTkTextbox = _FakeTextbox
    ctk.CTkButton = _FakeWidget
    ctk.CTkOptionMenu = _FakeOptionMenu
    ctk.CTkEntry = _FakeEntry
    ctk.CTkSwitch = _FakeSwitch
    ctk.CTkToplevel = _FakeWidget
    ctk.set_appearance_mode = lambda _m: None
    ctk.set_default_color_theme = lambda _m: None

    tk = types.ModuleType("tkinter")
    tk.StringVar = _FakeStringVar

    messagebox = types.SimpleNamespace(
        showinfo=lambda *_a, **_k: None, showerror=lambda *_a, **_k: None
    )
    tk.messagebox = messagebox

    sys.modules["customtkinter"] = ctk
    sys.modules["tkinter"] = tk


def _sample_pr() -> PullRequest:
    return PullRequest(
        repo="octo/repo",
        number=1,
        title="Title",
        author="octocat",
        state="OPEN",
        body="Description",
        base_branch="main",
        head_branch="feat",
        html_url="https://example",
        updated_at=datetime.now(),
        files=PRFileSummary(additions=2, deletions=1, changed_files=1),
        ci_status=CIStatus(state="SUCCESS"),
        file_changes=[PRFileChange(path="src/main.py", status="modified", patch="+a\n-b")],
        review_comments=[PRReviewComment(author="reviewer", body="Looks good")],
    )


def test_views_headless() -> None:
    _install_fake_gui_modules()

    import src.ui.views.pr_detail_view as detail_view_mod
    import src.ui.views.pr_list_view as list_view_mod
    import src.ui.views.settings_view as settings_view_mod

    selected: list[PullRequest] = []
    list_view = list_view_mod.PRListView(_FakeWidget(), on_select=lambda pr: selected.append(pr))
    pr = _sample_pr()
    list_view.set_items([pr])
    list_view.listbox._current_index = "1.0"  # type: ignore[attr-defined]
    list_view._handle_click(object())
    assert selected and selected[0].number == 1

    called: list[tuple[str, str | None]] = []
    detail = detail_view_mod.PRDetailView(
        _FakeWidget(),
        on_action=lambda action, _pr, comment, _m, _p, _n: called.append((action, comment)),
    )
    detail.set_pr(pr)
    assert "Changed Files:" in detail.body._text
    assert "Patch:" in detail.body._text
    assert "\u001b[" not in detail.body._text
    detail.comment_input.insert("1.0", "Ship it")
    detail._trigger("approve")
    assert called and called[0][0] == "approve"

    saved: list[AppConfig] = []
    dialog = settings_view_mod.SettingsDialog(
        _FakeWidget(),
        initial_config=AppConfig(),
        on_save=lambda config: saved.append(config),
    )
    dialog.repo_box.insert("1.0", "octo/repo\n")
    dialog.poll_interval.insert(0, "60")
    dialog.webhook_port.insert(0, "8765")
    dialog._save()
    assert saved


def test_app_headless() -> None:
    _install_fake_gui_modules()

    import src.ui.app as app_mod

    notification_service = types.SimpleNamespace(subscribe=lambda *_a, **_k: None)
    pr_service = types.SimpleNamespace(
        subscribe_updates=lambda *_a, **_k: None,
        subscribe_error=lambda *_a, **_k: None,
        notification_service=notification_service,
        start=lambda: None,
        stop=lambda: None,
        run_action=lambda **_k: None,
        force_refresh=lambda: None,
        get_pull_request_details=lambda pr: pr,
        gateway=types.SimpleNamespace(token="token"),
    )

    app = app_mod.PRMonitorApp(settings=AppSettings(config=AppConfig()), pr_service=pr_service)
    pr = _sample_pr()
    app._on_prs_updated([pr], datetime.now())
    app._on_polling_error("err")
    app._on_connection_status("connection_status", "ok")
    app._on_pr_selected(pr)
    app._on_action("approve", pr, "nice", "merge", None, None)

    app_mod.PRService = lambda settings, token: pr_service  # type: ignore[assignment]
    app._save_settings(AppConfig())
    app._open_settings()
    app._on_close()
