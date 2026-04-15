"""Tests for archive deduplication and skip-download behavior."""

from pathlib import Path
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
        qhook_factory=kwargs.get("qhook_factory", lambda: MagicMock()),
        qlogger_factory=kwargs.get("qlogger_factory", lambda: MagicMock(debug=Mock())),
    )


def test_skip_downloading_appends_new_ids(tmp_path) -> None:
    service = make_service()

    archive_path = tmp_path / "tfarchive.txt"
    archive_path.write_text("youtube abc123\n")

    def fake_path(path_str):
        return tmp_path / Path(path_str).name

    with patch("src.download_service.Path", side_effect=fake_path):
        with patch("src.download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = {
                "entries": [
                    {"id": "abc123"},
                    {"id": "def456"},
                ],
            }
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

            service.skip_downloading(
                ["https://youtube.com/watch?v=test"], "audio_playlists"
            )

    contents = archive_path.read_text().splitlines()
    assert "youtube abc123" in contents
    assert "youtube def456" in contents
    assert len(contents) == 2
    service.handle_queue_empty_callback.assert_called_once()


def test_skip_downloading_creates_archive_if_missing(tmp_path) -> None:
    service = make_service()

    def fake_path(path_str):
        return tmp_path / Path(path_str).name

    with patch("src.download_service.Path", side_effect=fake_path):
        with patch("src.download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = {
                "entries": [{"id": "newid"}],
            }
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

            service.skip_downloading(
                ["https://youtube.com/watch?v=test"], "audio_playlists"
            )

    archive_path = tmp_path / "tfarchive.txt"
    assert archive_path.exists()
    assert archive_path.read_text().strip() == "youtube newid"
