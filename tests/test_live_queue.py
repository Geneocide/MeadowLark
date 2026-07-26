"""Unit tests for live queue management — both standalone module and DownloadService wrappers."""

from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.download_service import DownloadService
from src.live_queue import add_to_live_queue, load_live_queue, save_live_queue

# --- Standalone src/live_queue module tests ---


@pytest.fixture
def queue_file(tmp_path: Path) -> Path:
    return tmp_path / "live_queue.txt"


def test_load_missing_file_returns_empty(queue_file: Path) -> None:
    assert load_live_queue(queue_file) == {}


def test_round_trip_without_playlist_id(queue_file: Path) -> None:
    entries = {"https://yt.com/watch?v=abc": ("youtube", None, None)}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_round_trip_with_playlist_id(queue_file: Path) -> None:
    entries = {"https://yt.com/watch?v=abc": ("youtube", "PLxyz", None)}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_add_creates_entry(queue_file: Path) -> None:
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube")
    result = load_live_queue(queue_file)
    assert result["https://yt.com/watch?v=xyz"] == ("youtube", None, None)


def test_add_deduplicates(queue_file: Path) -> None:
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube")
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube", "PLabc")
    result = load_live_queue(queue_file)
    assert len(result) == 1
    assert result["https://yt.com/watch?v=xyz"] == ("youtube", "PLabc", None)


def test_load_skips_blank_lines(queue_file: Path) -> None:
    queue_file.write_text("\nyoutube|https://yt.com/watch?v=abc\n\n", encoding="utf-8")
    result = load_live_queue(queue_file)
    assert len(result) == 1


# --- Boundary tests: label field (4th column) round-trip and malformed lines ---


def test_round_trip_with_label_no_playlist_id(queue_file: Path) -> None:
    entries = {"https://yt.com/watch?v=abc": ("audio_playlists", None, "Show Name")}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_round_trip_label_containing_pipe(queue_file: Path) -> None:
    """A label that itself contains '|' must survive intact, not get split into extra fields."""
    entries = {"https://yt.com/watch?v=abc": ("audio_playlists", "PLxyz", "Show | Two")}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_round_trip_unicode_and_very_long_label(queue_file: Path) -> None:
    label = ("配信番組 podcast show 🎙️ " * 30).strip()
    entries = {"https://yt.com/watch?v=abc": ("audio_playlists", None, label)}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_empty_label_round_trips_as_none(queue_file: Path) -> None:
    """
    An empty-string label is falsy at save time.

    It collapses to a 3-field legacy line and reloads as None rather than ''.
    """
    entries = {"https://yt.com/watch?v=abc": ("audio_playlists", "PLxyz", "")}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == {
        "https://yt.com/watch?v=abc": ("audio_playlists", "PLxyz", None),
    }


def test_load_legacy_two_field_line(queue_file: Path) -> None:
    """Lines written before playlist_id existed still parse with both trailing fields None."""
    queue_file.write_text("youtube|https://yt.com/watch?v=abc\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {
        "https://yt.com/watch?v=abc": ("youtube", None, None),
    }


def test_load_empty_playlist_id_with_label_present(queue_file: Path) -> None:
    """A line with an empty playlist_id column but a populated label column."""
    queue_file.write_text(
        "audio_playlists|https://yt.com/watch?v=abc||ShowLabel\n", encoding="utf-8"
    )
    assert load_live_queue(queue_file) == {
        "https://yt.com/watch?v=abc": ("audio_playlists", None, "ShowLabel"),
    }


def test_load_skips_line_with_empty_url(queue_file: Path) -> None:
    queue_file.write_text("audio_playlists||label\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {}


def test_load_skips_single_field_line(queue_file: Path) -> None:
    """A line with no '|' at all (truncated/corrupt write) is ignored, not a crash."""
    queue_file.write_text("justsource\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {}


def test_load_skips_bare_pipe_line(queue_file: Path) -> None:
    queue_file.write_text("|\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {}


def test_load_whitespace_only_line_is_skipped(queue_file: Path) -> None:
    queue_file.write_text("   \n\t\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {}


def test_load_trailing_pipes_become_literal_label(queue_file: Path) -> None:
    """
    Documents current parsing behavior for stray trailing pipes.

    split(maxsplit=3) only protects the LAST field from stray '|'. Pipes past the
    3rd delimiter are kept verbatim as the label rather than raising or being dropped.
    """
    queue_file.write_text("a|b|||\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {"b": ("a", None, "|")}


def test_load_pipe_in_playlist_id_mangles_label(queue_file: Path) -> None:
    """
    Known quirk (low severity): a playlist_id containing '|' mangles the label.

    Its remainder bleeds into the label field, since only the label (last field) is
    protected from further splitting. Real playlist IDs are alphanumeric so this
    shouldn't occur in practice -- documented here rather than fixed, per review scope.
    """
    queue_file.write_text("source|url|pl|ist|label\n", encoding="utf-8")
    assert load_live_queue(queue_file) == {"url": ("source", "pl", "ist|label")}


# --- DownloadService wrapper tests ---


def make_service(**kwargs):
    return DownloadService(
        download_queue=kwargs.get("download_queue", Queue()),
        ignore_archive_callback=kwargs.get("ignore_archive_callback", lambda: True),
        skip_download_callback=kwargs.get("skip_download_callback", lambda: False),
        label_output_set_text_callback=kwargs.get(
            "label_output_set_text_callback",
            Mock(),
        ),
        log_edit_append_callback=kwargs.get("log_edit_append_callback", Mock()),
        bar_progress_set_range_callback=kwargs.get(
            "bar_progress_set_range_callback",
            Mock(),
        ),
        bar_progress_set_value_callback=kwargs.get(
            "bar_progress_set_value_callback",
            Mock(),
        ),
        handle_info_changed_callback=kwargs.get("handle_info_changed_callback", Mock()),
        handle_log_entry_callback=kwargs.get("handle_log_entry_callback", Mock()),
        handle_queue_empty_callback=kwargs.get("handle_queue_empty_callback", Mock()),
        do_updates_callback=kwargs.get("do_updates_callback", Mock()),
        add_to_live_queue_callback=kwargs.get("add_to_live_queue_callback", Mock()),
        qhook_factory=kwargs.get(
            "qhook_factory",
            lambda: MagicMock(info_changed=MagicMock()),
        ),
        qlogger_factory=kwargs.get(
            "qlogger_factory",
            lambda: MagicMock(message_changed=MagicMock()),
        ),
    )


def test_load_live_queue_parses_file(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("audio_playlists|https://example.com/video\n")

    service = make_service()
    service.live_queue_path = path

    entries = service.load_live_queue()

    assert entries == {"https://example.com/video": ("audio_playlists", None, None)}


def test_load_live_queue_parses_playlist_id(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("720playlists|https://youtube.com/watch?v=abc|PLtest123\n")

    service = make_service()
    service.live_queue_path = path

    entries = service.load_live_queue()

    assert entries == {"https://youtube.com/watch?v=abc": ("720playlists", "PLtest123", None)}


def test_save_live_queue_writes_entries(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    service = make_service()
    service.live_queue_path = path

    service.save_live_queue({"https://example.com/video": ("audio_playlists", None, None)})

    assert path.read_text().strip() == "audio_playlists|https://example.com/video"


def test_save_live_queue_writes_playlist_id(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    service = make_service()
    service.live_queue_path = path

    service.save_live_queue(
        {"https://example.com/video": ("720playlists", "PLtest123", None)}
    )

    assert (
        path.read_text().strip() == "720playlists|https://example.com/video|PLtest123"
    )


def test_live_queue_round_trip_with_playlist_id(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    service = make_service()
    service.live_queue_path = path

    original = {"https://youtube.com/watch?v=X": ("720playlists", "PLabc456", None)}
    service.save_live_queue(original)
    loaded = service.load_live_queue()

    assert loaded == original


def test_add_to_live_queue_deduplicates(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("audio_playlists|https://example.com/video\n")

    service = make_service()
    service.live_queue_path = path

    service.add_to_live_queue("https://example.com/video", "audio_playlists")
    contents = path.read_text().strip().splitlines()

    assert contents == ["audio_playlists|https://example.com/video"]


def test_get_options_with_skip_playlist_dialog_flag_does_not_error() -> None:
    """Verify DownloadService.get_options accepts skip_playlist_dialog without error."""
    service = make_service()

    options = service.get_options(
        ["https://youtube.com/watch?v=123"],
        "audio",
        skip_playlist_dialog=True,
    )

    assert options is not None
    assert isinstance(options, dict)


def test_make_match_filter_records_live_url() -> None:
    add_to_live_queue = Mock()
    log_callback = Mock()
    service = make_service(
        add_to_live_queue_callback=add_to_live_queue,
        log_edit_append_callback=log_callback,
    )

    match_filter = service.make_match_filter("audio_playlists")
    result = match_filter(
        {
            "is_live": True,
            "webpage_url": "https://youtube.com/live",
            "live_status": "is_live",
        },
        False,
    )

    assert "Skipping live" in result
    add_to_live_queue.assert_called_once_with(
        "https://youtube.com/live",
        "audio_playlists",
        None,
        label=None,
    )
    log_callback.assert_called_once()


def test_make_match_filter_captures_playlist_id() -> None:
    add_to_live_queue = Mock()
    service = make_service(add_to_live_queue_callback=add_to_live_queue)

    match_filter = service.make_match_filter("720playlists")
    match_filter(
        {
            "is_live": True,
            "webpage_url": "https://youtube.com/watch?v=abc",
            "live_status": "is_live",
            "playlist_id": "PLxyz789",
        },
        False,
    )

    add_to_live_queue.assert_called_once_with(
        "https://youtube.com/watch?v=abc",
        "720playlists",
        "PLxyz789",
        label=None,
    )


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.load_playlist_comments_for_source",
    return_value={"PLtest": "Taskmaster S21"},
)
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_queues_ended_stream(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("720playlists|https://youtube.com/watch?v=ended|PLtest\n")

    queue = MagicMock()
    qhook = MagicMock(info_changed=MagicMock())
    qlogger = MagicMock(message_changed=MagicMock())

    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: qhook,
        qlogger_factory=lambda: qlogger,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {
        "is_live": False,
        "live_status": None,
    }
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    queue.put.assert_called_once()
    assert path.read_text().strip() == ""


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.load_playlist_comments_for_source",
    return_value={"PLtest": "Taskmaster S21"},
)
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_passes_playlist_comments_in_qmeta(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("720playlists|https://youtube.com/watch?v=ended|PLtest\n")

    queue = MagicMock()
    qhook = MagicMock(info_changed=MagicMock())
    qlogger = MagicMock(message_changed=MagicMock())

    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: qhook,
        qlogger_factory=lambda: qlogger,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"is_live": False, "live_status": None}
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    queued_urls, queued_opts = queue.put.call_args[0][0]
    assert queued_opts["qmeta"]["playlist_comments"] == {"PLtest": "Taskmaster S21"}
    assert queued_opts["qmeta"]["playlist_id"] == "PLtest"


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.load_playlist_comments_for_source", return_value={})
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_does_not_apply_match_filter(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("720playlists|https://youtube.com/watch?v=ended\n")

    queue = MagicMock()
    qhook = MagicMock(info_changed=MagicMock())
    qlogger = MagicMock(message_changed=MagicMock())

    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: qhook,
        qlogger_factory=lambda: qlogger,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"is_live": False, "live_status": None}
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    queued_urls, queued_opts = queue.put.call_args[0][0]
    assert "match_filter" not in queued_opts


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_extract_info_returns_none_keeps_entry_no_crash(
    mock_build_base,
    mock_ydl_class,
    tmp_path,
) -> None:
    """extract_info returning None must not raise AttributeError; entry stays queued."""
    path = tmp_path / "live_queue.txt"
    path.write_text("1080playlists|https://youtube.com/watch?v=ghost\n")

    queue = MagicMock()
    service = make_service(download_queue=queue)
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = None
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()  # must not raise

    queue.put.assert_not_called()
    assert "ghost" in path.read_text()


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_extract_info_returns_none_mixed_entries(
    mock_build_base,
    mock_ydl_class,
    tmp_path,
) -> None:
    """When one entry returns None and another is ended, only the ended one is queued."""
    path = tmp_path / "live_queue.txt"
    path.write_text(
        "1080playlists|https://youtube.com/watch?v=ghost\n"
        "1080playlists|https://youtube.com/watch?v=ended\n"
    )

    queue = MagicMock()
    qhook = MagicMock(info_changed=MagicMock())
    qlogger = MagicMock(message_changed=MagicMock())

    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: qhook,
        qlogger_factory=lambda: qlogger,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    def side_effect(url, download):
        if "ghost" in url:
            return None
        return {"is_live": False, "live_status": None}

    mock_instance = MagicMock()
    mock_instance.extract_info.side_effect = side_effect
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    with patch(
        "src.download_service.utils.load_playlist_comments_for_source", return_value={}
    ), patch(
        "src.download_service.utils.detect_site_from_urls", return_value="youtube"
    ):
        service.check_live_queue()

    queue.put.assert_called_once()
    remaining = path.read_text()
    assert "ghost" in remaining
    assert "ended" not in remaining


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_keeps_still_live_entry(
    mock_build_base,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("1080playlists|https://youtube.com/watch?v=live\n")

    queue = MagicMock()
    service = make_service(download_queue=queue)
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {
        "is_live": True,
        "live_status": "is_live",
    }
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    queue.put.assert_not_called()
    assert path.read_text().strip() == "1080playlists|https://youtube.com/watch?v=live"


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.load_playlist_comments_for_source", return_value={})
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_with_playlist_url_no_crash(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("1080playlists|https://youtube.com/watch?v=ended&list=WL\n")

    queue = MagicMock()
    service = make_service(
        download_queue=queue,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"is_live": False, "live_status": None}
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    queue.put.assert_called_once()
    assert path.read_text().strip() == ""


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_logs_all_error_types(
    mock_build_base,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text(
        "1080playlists|https://youtube.com/watch?v=ydl_error\n"
        "1080playlists|https://youtube.com/watch?v=runtime_error\n"
    )

    queue = MagicMock()
    log_callback = Mock()
    service = make_service(
        download_queue=queue,
        log_edit_append_callback=log_callback,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    def extract_info_side_effect(url, download):
        if "ydl_error" in url:
            raise OSError("extraction failed")
        return {"is_live": False, "live_status": None}

    mock_instance = MagicMock()
    mock_instance.extract_info.side_effect = extract_info_side_effect
    mock_ydl_class.return_value.__enter__.return_value = mock_instance
    service.get_options = MagicMock(side_effect=RuntimeError("unexpected"))  # type: ignore[method-assign]

    service.check_live_queue()

    assert log_callback.call_count >= 2
    remaining = path.read_text().strip().splitlines()
    assert any("ydl_error" in line for line in remaining)
    assert any("runtime_error" in line for line in remaining)


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.load_playlist_comments_for_source", return_value={})
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_saves_queue_after_processing(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path,
) -> None:
    """Verify that save_live_queue is called so ended items are removed from the file."""
    path = tmp_path / "live_queue.txt"
    path.write_text(
        "720playlists|https://youtube.com/watch?v=ended\n"
        "720playlists|https://youtube.com/watch?v=still_live\n",
    )

    queue = MagicMock()
    qhook = MagicMock(info_changed=MagicMock())
    qlogger = MagicMock(message_changed=MagicMock())

    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: qhook,
        qlogger_factory=lambda: qlogger,
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    def side_effect_info(url, download):
        if "still_live" in url:
            return {"is_live": True, "live_status": "is_live"}
        return {"is_live": False, "live_status": None}

    mock_instance = MagicMock()
    mock_instance.extract_info.side_effect = side_effect_info
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    remaining = path.read_text().strip()
    assert "ended" not in remaining
    assert "still_live" in remaining
