"""
Tests for MyWindow._show_failed_downloads reopen behaviour.

The dialog has no WA_DeleteOnClose, so closing it hides the widget without
destroying it. The cached instance must therefore be re-shown, not merely
raised, or the button silently no-ops after the first close.
"""

from unittest.mock import MagicMock

import pytest


def _make_window(existing: MagicMock | None) -> MagicMock:
    """Return a stub window wired to the real _show_failed_downloads body."""
    import meadowlark

    win = MagicMock()
    win._failed_dialog = existing
    win._show_failed_downloads = meadowlark.MyWindow._show_failed_downloads.__get__(win)
    return win


def test_cached_hidden_dialog_is_shown_again() -> None:
    """A closed-but-alive dialog must be re-shown, raised, and focused."""
    dialog = MagicMock()
    win = _make_window(dialog)

    win._show_failed_downloads()

    dialog.show.assert_called_once()
    dialog.raise_.assert_called_once()
    dialog.activateWindow.assert_called_once()
    assert win._failed_dialog is dialog


def test_dead_cached_dialog_falls_through_to_a_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the cached C++ object is gone, a fresh dialog replaces it."""
    import meadowlark

    dialog = MagicMock()
    dialog.show.side_effect = RuntimeError("wrapped C/C++ object has been deleted")
    win = _make_window(dialog)

    replacement = MagicMock()
    monkeypatch.setattr(
        meadowlark, "FailedDownloadsDialog", lambda *_args, **_kwargs: replacement
    )
    monkeypatch.setattr(meadowlark, "load_failed_downloads", lambda _path: [])

    win._show_failed_downloads()

    replacement.show.assert_called_once()
    assert win._failed_dialog is replacement
