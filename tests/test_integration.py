"""Integration-style tests for DownloadService behavior across request and queue flows."""

from queue import Queue
from unittest.mock import MagicMock, Mock

from src.download_service import DownloadService


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
        qhook_factory=kwargs.get("qhook_factory", MagicMock),
        qlogger_factory=kwargs.get("qlogger_factory", MagicMock),
    )


def test_request_detected_audio_playlists_returns_podcast_check() -> None:
    service = make_service()
    action, urls, ydl_opts = service.request_detected(
        ["https://youtube.com/watch?v=abc123"],
        "audio_playlists",
    )

    assert action == "podcast_check"
    assert urls == ["https://youtube.com/watch?v=abc123"]
    assert ydl_opts["qmeta"]["type"] == "audio_playlists"
    assert ydl_opts["format"] == "m4a/bestaudio/best"
    assert "outtmpl" in ydl_opts
    assert ydl_opts["postprocessors"] == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
    ]


def test_request_detected_1080playlists_returns_queue_action() -> None:
    service = make_service()
    action, urls, ydl_opts = service.request_detected(
        ["https://youtube.com/playlist?list=PL123"],
        "1080playlists",
    )

    assert action == "queue"
    assert urls == ["https://youtube.com/playlist?list=PL123"]
    assert ydl_opts["qmeta"]["site"] == "youtube"
    assert ydl_opts["format"].startswith("bestvideo*[height=1080]")
