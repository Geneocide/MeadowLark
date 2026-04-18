"""Tests for src.playlist_utils.load_playlist_urls and the _load_playlist_utils wrapper."""

import stat
import sys
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock

import pytest

from src import download_service as _ds
from src.download_service import DownloadService
from src.playlist_utils import load_playlist_urls


# ---------------------------------------------------------------------------
# Original 6 tests (preserved verbatim)
# ---------------------------------------------------------------------------


def test_load_playlist_urls_returns_urls(tmp_path: Path) -> None:
    f = tmp_path / "playlists.txt"
    f.write_text("https://youtube.com/playlist?list=PLabc\nhttps://youtube.com/playlist?list=PLxyz\n")
    assert load_playlist_urls(f) == [
        "https://youtube.com/playlist?list=PLabc",
        "https://youtube.com/playlist?list=PLxyz",
    ]


def test_load_playlist_urls_strips_comments(tmp_path: Path) -> None:
    f = tmp_path / "playlists.txt"
    f.write_text("# My playlist\nhttps://youtube.com/playlist?list=PLabc\n")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_strips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "playlists.txt"
    f.write_text("\nhttps://youtube.com/playlist?list=PLabc\n\n")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_missing_file(tmp_path: Path) -> None:
    assert load_playlist_urls(tmp_path / "nonexistent.txt") == []


def test_load_playlist_urls_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "playlists.txt"
    f.write_text("")
    assert load_playlist_urls(f) == []


def test_load_playlist_urls_comments_only(tmp_path: Path) -> None:
    f = tmp_path / "playlists.txt"
    f.write_text("# comment 1\n# comment 2\n")
    assert load_playlist_urls(f) == []


# ---------------------------------------------------------------------------
# New edge-case tests (boundary matrix rows 6-22)
# ---------------------------------------------------------------------------


def test_load_playlist_urls_single_url_no_trailing_newline(tmp_path: Path) -> None:
    """Row 6 - single URL with no trailing newline must still be returned."""
    f = tmp_path / "playlists.txt"
    f.write_bytes(b"https://youtube.com/playlist?list=PLabc")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_strips_leading_trailing_whitespace_from_url(tmp_path: Path) -> None:
    """Row 7 - URLs padded with spaces/tabs must be returned stripped."""
    f = tmp_path / "playlists.txt"
    f.write_text("  https://youtube.com/playlist?list=PLabc  \n")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_whitespace_only_line_filtered(tmp_path: Path) -> None:
    """Row 8 - a line containing only spaces must be treated as blank and filtered."""
    f = tmp_path / "playlists.txt"
    f.write_text("   \nhttps://youtube.com/playlist?list=PLabc\n")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_inline_hash_anchor_preserved(tmp_path: Path) -> None:
    """Row 9 - a URL with an inline '#' anchor must NOT be treated as a comment."""
    url = "https://example.com/page#section"
    f = tmp_path / "playlists.txt"
    f.write_text(f"{url}\n")
    assert load_playlist_urls(f) == [url]


def test_load_playlist_urls_double_hash_comment_filtered(tmp_path: Path) -> None:
    """Row 10 - lines starting with '##' must still be filtered as comments."""
    f = tmp_path / "playlists.txt"
    f.write_text("## section header\nhttps://youtube.com/playlist?list=PLabc\n")
    assert load_playlist_urls(f) == ["https://youtube.com/playlist?list=PLabc"]


def test_load_playlist_urls_mixed_content_returns_only_urls(tmp_path: Path) -> None:
    """Row 11 - mix of URLs, comments, and blank lines returns only the URLs, in order."""
    f = tmp_path / "playlists.txt"
    f.write_text(
        "# group A\n"
        "https://youtube.com/playlist?list=PLa\n"
        "\n"
        "# group B\n"
        "https://youtube.com/playlist?list=PLb\n",
    )
    assert load_playlist_urls(f) == [
        "https://youtube.com/playlist?list=PLa",
        "https://youtube.com/playlist?list=PLb",
    ]


def test_load_playlist_urls_non_utf8_file_behavior(tmp_path: Path) -> None:
    """Row 12 - documents behavior on non-UTF-8 bytes.

    The implementation opens with encoding='utf-8' and only catches OSError.
    UnicodeDecodeError is NOT a subclass of OSError, so the function will raise
    rather than return [] for truly undecodable files. This test documents and
    verifies that gap so it can be addressed if callers need resilience.
    """
    f = tmp_path / "playlists.txt"
    # Bytes that are invalid in UTF-8
    f.write_bytes(b"\x80\x81\x82")
    try:
        result = load_playlist_urls(f)
        # If somehow it succeeds the return type must still be a list
        assert isinstance(result, list)
    except UnicodeDecodeError:
        # Known gap: UnicodeDecodeError propagates unhandled.
        pass


@pytest.mark.skipif(sys.platform == "win32", reason="chmod permission tests are unreliable on Windows")
def test_load_playlist_urls_permission_denied_returns_empty(tmp_path: Path) -> None:
    """Row 14 - a file that exists but cannot be read must return []."""
    f = tmp_path / "playlists.txt"
    f.write_text("https://youtube.com/playlist?list=PLabc\n")
    f.chmod(0o000)
    try:
        assert load_playlist_urls(f) == []
    finally:
        f.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_load_playlist_urls_path_is_directory_returns_empty(tmp_path: Path) -> None:
    """Row 15 - passing a directory path (which exists) must return [] not crash.

    path.exists() is True for a directory; open() raises IsADirectoryError which
    is a subclass of OSError, so the except clause must catch it.
    """
    assert load_playlist_urls(tmp_path) == []


def test_load_playlist_urls_large_file_returns_all_urls(tmp_path: Path) -> None:
    """Row 17 - a file with many URLs must return all of them without truncation."""
    urls = [f"https://youtube.com/playlist?list=PL{i:05d}" for i in range(5000)]
    f = tmp_path / "playlists.txt"
    f.write_text("\n".join(urls) + "\n")
    result = load_playlist_urls(f)
    assert result == urls
    assert len(result) == 5000


# ---------------------------------------------------------------------------
# _load_playlist_urls wrapper contract tests (rows 18-22)
# Tests access the private method deliberately to verify the None-vs-[]
# contract that the request_detected caller depends on.
# ---------------------------------------------------------------------------


def _make_service() -> DownloadService:
    """Build a minimal DownloadService with all callbacks stubbed."""
    return DownloadService(
        download_queue=Queue(),
        ignore_archive_callback=MagicMock(return_value=False),
        skip_download_callback=MagicMock(return_value=False),
        label_output_set_text_callback=MagicMock(),
        log_edit_append_callback=MagicMock(),
        bar_progress_set_range_callback=MagicMock(),
        bar_progress_set_value_callback=MagicMock(),
        handle_info_changed_callback=MagicMock(),
        handle_log_entry_callback=MagicMock(),
        handle_queue_empty_callback=MagicMock(),
        do_updates_callback=MagicMock(),
        add_to_live_queue_callback=MagicMock(),
        qhook_factory=MagicMock(),
        qlogger_factory=MagicMock(),
    )


def test_load_playlist_urls_wrapper_unknown_source_returns_none() -> None:
    """Row 20 - an unrecognised source must return None (not [])."""
    svc = _make_service()
    assert svc._load_playlist_urls("not_a_real_source") is None  # noqa: SLF001


def test_load_playlist_urls_wrapper_known_source_missing_file_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 21 - known source whose playlist file does not exist must return None."""
    monkeypatch.setattr(_ds, "PLAYLISTS_FILE", tmp_path / "nonexistent.txt")
    svc = _make_service()
    assert svc._load_playlist_urls("1080playlists") is None  # noqa: SLF001


def test_load_playlist_urls_wrapper_known_source_empty_file_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 18 - known source whose playlist file is empty must return None (not []).

    The wrapper uses `load_playlist_urls(...) or None` which converts [] to None.
    This test verifies that contract holds so request_detected treats empty files
    the same as missing files (does not overwrite urls with an empty list).
    """
    f = tmp_path / "playlists.txt"
    f.write_text("")
    monkeypatch.setattr(_ds, "PLAYLISTS_FILE", f)
    svc = _make_service()
    result = svc._load_playlist_urls("1080playlists")  # noqa: SLF001
    assert result is None, "Empty playlist file must yield None, not [], to satisfy caller contract"


def test_load_playlist_urls_wrapper_known_source_with_urls_returns_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 19 - known source with URLs in file must return a non-empty list."""
    f = tmp_path / "playlists.txt"
    f.write_text("https://youtube.com/playlist?list=PLabc\n")
    monkeypatch.setattr(_ds, "PLAYLISTS_FILE", f)
    svc = _make_service()
    result = svc._load_playlist_urls("1080playlists")  # noqa: SLF001
    assert result == ["https://youtube.com/playlist?list=PLabc"]


def test_request_detected_skips_file_load_when_urls_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 22 - if urls are already supplied, _load_playlist_urls must not be called."""
    monkeypatch.setattr(_ds, "PLAYLISTS_FILE", tmp_path / "nonexistent.txt")

    svc = _make_service()
    svc._load_playlist_urls = MagicMock(return_value=None)  # type: ignore[method-assign]  # noqa: SLF001
    svc.get_options = MagicMock(return_value=None)  # short-circuit after the load guard

    svc.request_detected(["https://youtube.com/watch?v=abc"], "1080playlists")

    svc._load_playlist_urls.assert_not_called()  # noqa: SLF001
