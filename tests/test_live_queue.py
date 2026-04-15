"""Unit tests for live queue management in DownloadService."""

from queue import Queue
from unittest.mock import MagicMock, Mock, patch

from src.download_service import DownloadService


def make_service(**kwargs):
    return DownloadService(
        download_queue=kwargs.get("download_queue", Queue()),
        ignore_archive_callback=kwargs.get("ignore_archive_callback", lambda: True),
        skip_download_callback=kwargs.get("skip_download_callback", lambda: False),
        label_output_set_text_callback=kwargs.get(
            "label_output_set_text_callback", Mock()
        ),
        log_edit_append_callback=kwargs.get("log_edit_append_callback", Mock()),
        bar_progress_set_range_callback=kwargs.get(
            "bar_progress_set_range_callback", Mock()
        ),
        bar_progress_set_value_callback=kwargs.get(
            "bar_progress_set_value_callback", Mock()
        ),
        handle_info_changed_callback=kwargs.get("handle_info_changed_callback", Mock()),
        handle_log_entry_callback=kwargs.get("handle_log_entry_callback", Mock()),
        handle_queue_empty_callback=kwargs.get("handle_queue_empty_callback", Mock()),
        do_updates_callback=kwargs.get("do_updates_callback", Mock()),
        add_to_live_queue_callback=kwargs.get("add_to_live_queue_callback", Mock()),
        qhook_factory=kwargs.get(
            "qhook_factory", lambda: MagicMock(info_changed=MagicMock())
        ),
        qlogger_factory=kwargs.get(
            "qlogger_factory", lambda: MagicMock(message_changed=MagicMock())
        ),
    )


def test_load_live_queue_parses_file(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("audio_playlists|https://example.com/video\n")

    service = make_service()
    service.live_queue_path = path

    entries = service.load_live_queue()

    assert entries == {"https://example.com/video": "audio_playlists"}


def test_save_live_queue_writes_entries(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    service = make_service()
    service.live_queue_path = path

    service.save_live_queue({"https://example.com/video": "audio_playlists"})

    assert path.read_text().strip() == "audio_playlists|https://example.com/video"


def test_add_to_live_queue_deduplicates(tmp_path) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("audio_playlists|https://example.com/video\n")

    service = make_service()
    service.live_queue_path = path

    service.add_to_live_queue("https://example.com/video", "audio_playlists")
    contents = path.read_text().strip().splitlines()

    assert contents == ["audio_playlists|https://example.com/video"]


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
        "https://youtube.com/live", "audio_playlists"
    )
    log_callback.assert_called_once()


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_queues_ended_stream(
    mock_build_base,
    mock_detect_site,
    mock_ydl_class,
    tmp_path,
) -> None:
    path = tmp_path / "live_queue.txt"
    path.write_text("1080playlists|https://youtube.com/watch?v=ended\n")

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
