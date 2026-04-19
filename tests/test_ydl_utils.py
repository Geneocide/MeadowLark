"""Unit tests for src.ydl_utils."""
# ruff: noqa: S101

from collections.abc import Callable
from unittest.mock import MagicMock

from src.ydl_utils import extract_playlist_info, extract_video_entries

_PLAYLISTEND_SENTINEL = 5


def _make_ydl_factory(
    info: dict,
    captured_opts: list[dict] | None = None,
) -> Callable[[dict], MagicMock]:
    """Return a callable that acts as a YoutubeDL class, capturing opts if provided."""

    def factory(opts: dict) -> MagicMock:
        if captured_opts is not None:
            captured_opts.append(dict(opts))
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        mock.extract_info.return_value = info
        return mock

    return factory


def test_extract_playlist_info_returns_info() -> None:
    factory = _make_ydl_factory({"title": "test playlist"})
    result = extract_playlist_info("https://example.com", ydl_class=factory)
    assert result == {"title": "test playlist"}


def test_extract_playlist_info_without_playlistend_does_not_set_key() -> None:
    captured: list[dict] = []
    factory = _make_ydl_factory({}, captured_opts=captured)
    extract_playlist_info("https://example.com", playlistend=None, ydl_class=factory)
    assert "playlistend" not in captured[0]


def test_extract_playlist_info_with_playlistend_sets_key() -> None:
    captured: list[dict] = []
    factory = _make_ydl_factory({}, captured_opts=captured)
    extract_playlist_info(
        "https://example.com",
        playlistend=_PLAYLISTEND_SENTINEL,
        ydl_class=factory,
    )
    assert captured[0]["playlistend"] == _PLAYLISTEND_SENTINEL


def test_extract_video_entries_returns_entries_list() -> None:
    factory = _make_ydl_factory({"entries": [{"id": "v1"}, {"id": "v2"}]})
    entries = extract_video_entries("https://example.com", ydl_class=factory)
    assert entries == [{"id": "v1"}, {"id": "v2"}]


def test_extract_video_entries_wraps_single_video_in_list() -> None:
    info = {"id": "single_video", "title": "A Video"}
    factory = _make_ydl_factory(info)
    entries = extract_video_entries("https://example.com", ydl_class=factory)
    assert entries == [info]


def test_extract_playlist_info_uses_default_ydl_class_when_none() -> None:
    from unittest.mock import patch  # noqa: PLC0415

    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.extract_info.return_value = {"title": "default class"}

    with patch("src.ydl_utils.yt_dlp.YoutubeDL", return_value=mock_instance):
        result = extract_playlist_info("https://example.com")
    assert result == {"title": "default class"}


def test_extract_video_entries_uses_default_ydl_class_when_none() -> None:
    from unittest.mock import patch  # noqa: PLC0415

    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.extract_info.return_value = {"entries": [{"id": "v1"}]}

    with patch("src.ydl_utils.yt_dlp.YoutubeDL", return_value=mock_instance):
        entries = extract_video_entries("https://example.com")
    assert entries == [{"id": "v1"}]
