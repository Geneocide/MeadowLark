"""Unit tests for yt-dlp version and update utilities."""

from unittest.mock import MagicMock, Mock, patch

import requests

from src.version_utils import (
    get_current_yt_dlp_version,
    get_latest_yt_dlp_version,
    is_yt_dlp_update_available,
    normalize_version,
)


def test_normalize_version_parses_numeric_segments() -> None:
    assert normalize_version("2025.08.27") == (2025, 8, 27)
    assert normalize_version("2025.8.27") == (2025, 8, 27)
    assert normalize_version("1.2") == (1, 2)


def test_normalize_version_returns_empty_for_invalid_input() -> None:
    assert normalize_version("") == ()
    assert normalize_version(None) == ()  # type: ignore
    assert normalize_version("abc") == ()


def test_get_current_yt_dlp_version_uses_version_attribute() -> None:
    module = MagicMock()
    module.version.__version__ = "2026.01.01"
    with patch("src.version_utils.yt_dlp", module):
        assert get_current_yt_dlp_version() == "2026.01.01"


def test_get_latest_yt_dlp_version_returns_none_on_error() -> None:
    with patch(
        "src.version_utils.requests.get",
        side_effect=requests.exceptions.RequestException("fail"),
    ):
        assert get_latest_yt_dlp_version() is None


def test_get_latest_yt_dlp_version_success() -> None:
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"info": {"version": "2026.02.02"}}
    with patch("src.version_utils.requests.get", return_value=response):
        assert get_latest_yt_dlp_version() == "2026.02.02"


def test_is_yt_dlp_update_available_detects_newer_version() -> None:
    with (
        patch(
            "src.version_utils.get_current_yt_dlp_version", return_value="2026.01.01"
        ),
        patch(
            "src.version_utils.get_latest_yt_dlp_version",
            return_value="2026.02.02",
        ),
    ):
        available, current, latest = is_yt_dlp_update_available()
        assert available is True
        assert current == (2026, 1, 1)
        assert latest == (2026, 2, 2)


def test_get_current_yt_dlp_version_falls_back_to_module_attribute() -> None:
    module = MagicMock()
    version_mock = MagicMock(spec=[])  # no __version__ in spec → AttributeError
    module.version = version_mock
    module.__version__ = "2026.03.03"
    with patch("src.version_utils.yt_dlp", module):
        result = get_current_yt_dlp_version()
    assert result == "2026.03.03"


def test_get_latest_yt_dlp_version_returns_none_for_non_200_status() -> None:
    response = Mock()
    response.status_code = 404
    with patch("src.version_utils.requests.get", return_value=response):
        assert get_latest_yt_dlp_version() is None


def test_get_current_yt_dlp_version_returns_none_on_import_error() -> None:
    class FakeYtDlp:
        @property
        def version(self):
            raise ImportError("yt_dlp.version not available")

    with patch("src.version_utils.yt_dlp", FakeYtDlp()):
        result = get_current_yt_dlp_version()
    assert result is None


def test_is_yt_dlp_update_available_returns_false_when_up_to_date() -> None:
    with (
        patch(
            "src.version_utils.get_current_yt_dlp_version", return_value="2026.02.02"
        ),
        patch(
            "src.version_utils.get_latest_yt_dlp_version",
            return_value="2026.02.02",
        ),
    ):
        available, current, latest = is_yt_dlp_update_available()
        assert available is False
        assert current == (2026, 2, 2)
        assert latest == (2026, 2, 2)
