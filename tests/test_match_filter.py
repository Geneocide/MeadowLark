"""Unit tests for src.match_filter.build_match_filter."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from src.match_filter import build_match_filter


def _make_mf(source: str = "1080playlists") -> Callable[[dict, bool], str | None]:
    return build_match_filter(source, MagicMock(), MagicMock())


def test_mf_skips_needs_auth() -> None:
    mf = _make_mf()
    result = mf({"availability": "needs_auth"}, False)
    assert result == "Skipping: needs_auth"


def test_mf_skips_scheduled() -> None:
    mf = _make_mf()
    result = mf({"availability": "scheduled"}, False)
    assert result == "Skipping: scheduled"


def test_mf_none_info_calls_log_exception_and_returns_none() -> None:
    mf = _make_mf()
    with patch("utils.log_exception") as mock_log:
        result = mf(None, False)  # type: ignore[arg-type]
    assert result is None
    mock_log.assert_called_once()


def test_mf_normal_video_returns_none() -> None:
    mf = _make_mf()
    result = mf(
        {"is_live": False, "live_status": "not_live", "availability": "public"}, False
    )
    assert result is None
