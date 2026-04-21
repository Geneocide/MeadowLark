"""Unit tests for DownloadService option building and request dispatching."""

from queue import Queue
from unittest.mock import MagicMock, Mock, patch

from src.config import ARCHIVE_PATH, PODCAST_MISC_OUTPUT_DIR
from src.download_service import DownloadService


def make_service(**kwargs):
    return DownloadService(
        download_queue=kwargs.get("download_queue", Queue()),
        ignore_archive_callback=kwargs.get("ignore_archive_callback", lambda: False),
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
        qhook_factory=kwargs.get("qhook_factory", MagicMock),
        qlogger_factory=kwargs.get("qlogger_factory", MagicMock),
    )


def test_request_detected_update_triggers_update_callback() -> None:
    callback = Mock()
    service = make_service(do_updates_callback=callback)

    action, urls, ydl_opts = service.request_detected(
        ["https://youtube.com/watch?v=1"],
        "Update",
    )

    assert action == "update"
    assert urls == []
    assert ydl_opts == {}
    callback.assert_called_once()


def test_get_options_returns_none_when_skip_download_called() -> None:
    service = make_service(skip_download_callback=lambda: True)
    with patch.object(service, "skip_downloading") as mock_skip_downloading:
        assert service.get_options(["https://youtube.com/watch?v=1"], "audio") is None
        mock_skip_downloading.assert_called_once_with(
            ["https://youtube.com/watch?v=1"],
            "audio",
        )


def test_get_options_returns_none_for_empty_urls() -> None:
    log_callback = Mock()
    service = make_service(log_edit_append_callback=log_callback)

    assert service.get_options([], "audio") is None
    log_callback.assert_called_once()
    assert "No URLs found" in log_callback.call_args[0][0]


def test_get_options_builds_youtube_source_options() -> None:
    service = make_service(ignore_archive_callback=lambda: True)
    options = service.get_options(["https://youtube.com/watch?v=123"], "audio")

    assert isinstance(options, dict)
    assert options["format"] == "m4a/bestaudio/best"
    assert options["outtmpl"].endswith("%(title)s.%(ext)s")
    assert options["match_filter"] is not None
    assert isinstance(options["postprocessors"], list)
    assert "download_archive" not in options


def test_load_playlist_urls_reads_existing_file(tmp_path, monkeypatch) -> None:
    playlist_file = tmp_path / "playlists.txt"
    playlist_file.write_text("https://example.com/video1\nhttps://example.com/video2\n")

    from src import download_service

    monkeypatch.setattr(download_service, "PLAYLISTS_FILE", playlist_file)
    monkeypatch.setattr(download_service, "PLAYLISTS_720_FILE", playlist_file)
    monkeypatch.setattr(download_service, "PLAYLISTS_AUDIO_FILE", playlist_file)

    service = make_service()
    urls = service._load_playlist_urls("1080playlists")

    assert urls == ["https://example.com/video1", "https://example.com/video2"]


def test_get_source_options_audio_playlists_has_ignore_errors() -> None:
    service = make_service()
    options = service.get_options(
        ["https://youtube.com/watch?v=123"],
        "audio_playlists",
    )

    assert options["ignoreerrors"] == "only_download"
    assert options["format"] == "m4a/bestaudio/best"
    assert options["outtmpl"].startswith(PODCAST_MISC_OUTPUT_DIR.as_posix())


def test_add_archive_if_needed_adds_path() -> None:
    service = make_service(ignore_archive_callback=lambda: False)
    props: dict = {}
    service._add_archive_if_needed(props)
    assert props.get("download_archive") == str(ARCHIVE_PATH)


def test_add_archive_if_needed_skips_when_ignored() -> None:
    service = make_service(ignore_archive_callback=lambda: True)
    props: dict = {}
    service._add_archive_if_needed(props)
    assert "download_archive" not in props


def test_add_match_filter_for_youtube_url() -> None:
    service = make_service()
    props: dict = {}
    service._add_match_filter_if_youtube(
        props, ["https://youtube.com/watch?v=abc"], "1080"
    )
    assert "match_filter" in props


def test_add_match_filter_skipped_for_non_youtube() -> None:
    service = make_service()
    props: dict = {}
    service._add_match_filter_if_youtube(props, ["https://twitch.tv/stream"], "1080")
    assert "match_filter" not in props


def test_strip_watch_later_list_param_removes_list() -> None:
    service = make_service()
    urls = ["https://youtube.com/watch?v=abc&list=WL&index=3"]
    service._strip_watch_later_list_param(urls)
    assert urls[0] == "https://youtube.com/watch?v=abc"


def test_strip_watch_later_list_param_leaves_playlist_url_alone() -> None:
    service = make_service()
    urls = ["https://youtube.com/playlist?list=PLabc"]
    service._strip_watch_later_list_param(urls)
    assert urls[0] == "https://youtube.com/playlist?list=PLabc"


# ---------------------------------------------------------------------------
# request_detected: playlist URL loading from file (lines 110-112)
# ---------------------------------------------------------------------------


def test_request_detected_loads_urls_from_file_when_empty_urls_provided() -> None:
    service = make_service()
    loaded_urls = ["https://youtube.com/playlist?list=PLabc"]
    service._load_playlist_urls = MagicMock(return_value=loaded_urls)  # type: ignore[method-assign]
    service.get_options = MagicMock(return_value=None)  # type: ignore[method-assign]

    service.request_detected([], "1080playlists")

    service._load_playlist_urls.assert_called_once_with("1080playlists")
    service.get_options.assert_called_once_with(loaded_urls, "1080playlists")


# ---------------------------------------------------------------------------
# check_live_queue: empty queue returns immediately (line 243)
# ---------------------------------------------------------------------------


def test_check_live_queue_empty_queue_does_not_call_save() -> None:
    service = make_service()
    service.load_live_queue = MagicMock(return_value={})  # type: ignore[method-assign]
    service.save_live_queue = MagicMock()  # type: ignore[method-assign]

    service.check_live_queue()

    service.load_live_queue.assert_called_once()
    service.save_live_queue.assert_not_called()


# ---------------------------------------------------------------------------
# check_live_queue: YDL extraction error keeps URL in remaining (lines 288-291)
# ---------------------------------------------------------------------------


def test_check_live_queue_ydl_error_keeps_url_in_remaining() -> None:
    log_callback = Mock()
    service = make_service(log_edit_append_callback=log_callback)

    queue_entries = {"https://youtube.com/watch?v=abc": ("1080playlists", None)}
    service.load_live_queue = MagicMock(return_value=queue_entries)  # type: ignore[method-assign]
    service.save_live_queue = MagicMock()  # type: ignore[method-assign]

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.side_effect = OSError("extraction failed")
        service.check_live_queue()

    saved_remaining = service.save_live_queue.call_args[0][0]
    assert "https://youtube.com/watch?v=abc" in saved_remaining
    log_callback.assert_called()
