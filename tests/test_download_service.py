"""Unit tests for DownloadService option building and request dispatching."""

from queue import Queue
from unittest.mock import MagicMock, Mock, patch

import pytest

from src import download_service
from src.config import ARCHIVE_PATH, PODCAST_MISC_OUTPUT_DIR
from src.download_service import DownloadService
from src.pending_queue import (
    KIND_LIVE,
    load_pending_queue,
    make_pending_record,
    save_pending_queue,
)


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


def test_get_options_accepts_skip_playlist_dialog_flag() -> None:
    service = make_service(ignore_archive_callback=lambda: True)

    options = service.get_options(
        ["https://youtube.com/watch?v=123"],
        "audio",
        skip_playlist_dialog=True,
    )

    assert isinstance(options, dict)
    assert options["match_filter"] is not None


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
# check_pending_queue: empty queue returns immediately
# ---------------------------------------------------------------------------


def test_check_pending_queue_empty_queue_does_not_call_save(tmp_path) -> None:
    service = make_service()
    service.pending_queue_path = tmp_path / "pending_queue.json"

    with patch("src.pending_check.save_pending_queue") as mock_save:
        result = service.check_pending_queue()

    assert result == []
    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# check_pending_queue: YDL extraction error keeps URL in remaining
# ---------------------------------------------------------------------------


def test_check_pending_queue_ydl_error_keeps_url_in_remaining(tmp_path) -> None:
    log_callback = Mock()
    service = make_service(log_edit_append_callback=log_callback)
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path, [make_pending_record("https://youtube.com/watch?v=abc", "1080playlists")]
    )

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.side_effect = OSError("extraction failed")
        service.check_pending_queue()

    remaining_urls = {r["url"] for r in load_pending_queue(path)}
    assert "https://youtube.com/watch?v=abc" in remaining_urls
    log_callback.assert_called()


def test_check_pending_queue_still_live_and_upcoming_preserved(tmp_path) -> None:
    """Verify still-live and upcoming URLs are preserved in queue and saved."""
    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path,
        [
            make_pending_record("https://youtube.com/watch?v=still_live", "1080playlists"),
            make_pending_record(
                "https://youtube.com/watch?v=upcoming",
                "720playlists",
                playlist_id="PLtest",
            ),
        ],
    )

    def extract_info_side_effect(url, download=False):
        if "still_live" in url:
            return {"is_live": True, "live_status": "is_live"}
        if "upcoming" in url:
            return {"is_live": False, "live_status": "is_upcoming"}
        return {"is_live": False, "live_status": None}

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.side_effect = extract_info_side_effect
        service.check_pending_queue()

    remaining = {r["url"]: r for r in load_pending_queue(path)}
    assert "https://youtube.com/watch?v=still_live" in remaining
    assert remaining["https://youtube.com/watch?v=still_live"]["source"] == "1080playlists"
    assert "https://youtube.com/watch?v=upcoming" in remaining
    assert remaining["https://youtube.com/watch?v=upcoming"]["playlist_id"] == "PLtest"


def test_check_pending_queue_generic_exception_keeps_url_in_remaining(tmp_path) -> None:
    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path, [make_pending_record("https://youtube.com/watch?v=abc", "1080playlists")]
    )
    service.get_options = MagicMock(side_effect=TypeError("unexpected"))  # type: ignore[method-assign]

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.return_value = {
            "is_live": False,
            "live_status": None,
        }
        service.check_pending_queue()

    remaining_urls = {r["url"] for r in load_pending_queue(path)}
    assert "https://youtube.com/watch?v=abc" in remaining_urls


def test_check_pending_queue_runtime_error_keeps_url_in_remaining(tmp_path) -> None:
    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path, [make_pending_record("https://youtube.com/watch?v=abc", "1080playlists")]
    )
    service.get_options = MagicMock(side_effect=RuntimeError("qt-like failure"))  # type: ignore[method-assign]

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.return_value = {
            "is_live": False,
            "live_status": None,
        }
        service.check_pending_queue()

    remaining_urls = {r["url"] for r in load_pending_queue(path)}
    assert "https://youtube.com/watch?v=abc" in remaining_urls


# ---------------------------------------------------------------------------
# skip_downloading / check_pending_queue: shared PO-token provider wiring
#
# Both build a YoutubeDL dict inline rather than via utils.build_base_ydl_opts,
# so they need build_shared_extraction_opts() merged in explicitly. A bare
# YoutubeDL here falls back to the bgutil provider's stale
# ~/bgutil-ytdlp-pot-provider default server_home, whose cold-cache Deno
# probe overruns yt-dlp's 15s budget -- the exact failure this fix addressed
# for podcast metadata extraction, just reached from a different call site.
# ---------------------------------------------------------------------------


def test_skip_downloading_carries_pot_provider_wiring(tmp_path) -> None:
    from src.config import POT_PROVIDER_SERVER_HOME

    service = make_service()
    archive_path = tmp_path / "archive.txt"

    with (
        patch("src.download_service.ARCHIVE_PATH", archive_path),
        patch("src.download_service.yt_dlp.YoutubeDL") as mock_ydl_class,
    ):
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {"entries": [{"id": "vid1"}]}
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        service.skip_downloading(
            ["https://youtube.com/watch?v=test"],
            "audio_playlists",
        )

    opts = mock_ydl_class.call_args.args[0]
    assert opts["extractor_args"]["youtubepot-bgutilscript"]["server_home"] == [
        str(POT_PROVIDER_SERVER_HOME)
    ]
    assert opts["extractor_args"]["youtube"]["player_client"]
    assert "js_runtimes" in opts
    # per-call key ("lists" in "audio_playlists" -> "in_playlist") must survive the merge
    assert opts["extract_flat"] == "in_playlist"


def test_skip_downloading_single_url_extract_flat_true_survives_merge(
    tmp_path,
) -> None:
    """Non-list sources use extract_flat=True; must also survive the opts merge."""
    service = make_service()
    archive_path = tmp_path / "archive.txt"

    with (
        patch("src.download_service.ARCHIVE_PATH", archive_path),
        patch("src.download_service.yt_dlp.YoutubeDL") as mock_ydl_class,
    ):
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {"entries": [{"id": "vid1"}]}
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        service.skip_downloading(["https://youtube.com/watch?v=test"], "1080")

    opts = mock_ydl_class.call_args.args[0]
    assert opts["extract_flat"] is True
    assert "extractor_args" in opts


def test_check_pending_queue_carries_pot_provider_wiring(tmp_path) -> None:
    from src.config import POT_PROVIDER_SERVER_HOME

    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path, [make_pending_record("https://youtube.com/watch?v=abc", "1080playlists")]
    )

    with patch("src.download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
        ydl_instance = mock_ydl_class.return_value.__enter__.return_value
        ydl_instance.extract_info.return_value = {
            "is_live": True,
            "live_status": "is_live",
        }
        service.check_pending_queue()

    opts = mock_ydl_class.call_args.args[0]
    assert opts["extractor_args"]["youtubepot-bgutilscript"]["server_home"] == [
        str(POT_PROVIDER_SERVER_HOME)
    ]
    assert opts["extractor_args"]["youtube"]["player_client"]
    assert "js_runtimes" in opts
    # extract_release_info's own opts must survive the merge
    assert opts["skip_download"] is True
    assert opts["ignore_no_formats_error"] is True
    assert opts["noplaylist"] is True
    assert opts["quiet"] is True


def test_check_pending_queue_keyboard_interrupt_not_caught(tmp_path) -> None:
    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path
    save_pending_queue(
        path, [make_pending_record("https://youtube.com/watch?v=abc", "1080playlists")]
    )
    service.get_options = MagicMock(side_effect=KeyboardInterrupt())  # type: ignore[method-assign]

    with patch("src.download_service.yt_dlp.YoutubeDL") as MockYDL:
        ydl_instance = MockYDL.return_value.__enter__.return_value
        ydl_instance.extract_info.return_value = {
            "is_live": False,
            "live_status": None,
        }
        with pytest.raises(KeyboardInterrupt):
            service.check_pending_queue()

    # save_pending_queue is only reached after the loop finishes; a KeyboardInterrupt
    # mid-loop must leave the on-disk store untouched.
    remaining_urls = {r["url"] for r in load_pending_queue(path)}
    assert "https://youtube.com/watch?v=abc" in remaining_urls


def test_add_to_live_queue_writes_pending_record(tmp_path) -> None:
    service = make_service()
    path = tmp_path / "pending_queue.json"
    service.pending_queue_path = path

    service.add_to_live_queue(
        "https://youtube.com/watch?v=abc", "1080playlists", "PLx", label="Show"
    )

    records = load_pending_queue(path)
    assert len(records) == 1
    assert records[0]["kind"] == KIND_LIVE
    assert records[0]["playlist_id"] == "PLx"
    assert records[0]["label"] == "Show"


def test_pending_deps_ydl_class_is_explicitly_wired_not_frozen_default(tmp_path) -> None:
    """
    ``_pending_deps`` must pass ``ydl_class`` explicitly, not rely on the dataclass default.

    ``PendingCheckDeps.ydl_class`` defaults to the real ``yt_dlp.YoutubeDL`` bound once
    at ``src.pending_check`` import time. If a future edit dropped the explicit
    ``ydl_class=yt_dlp.YoutubeDL`` kwarg from ``_pending_deps``, tests that patch
    ``src.download_service.yt_dlp.YoutubeDL`` would silently stop being honored and
    fall through to a real network call instead -- this test asserts the identity
    directly so that regression fails clearly instead of via a flaky network timeout.
    """
    service = make_service()
    service.pending_queue_path = tmp_path / "pending_queue.json"

    sentinel_class = type("SentinelYDL", (), {})
    with patch("src.download_service.yt_dlp.YoutubeDL", sentinel_class):
        deps = service._pending_deps()

    assert deps.ydl_class is sentinel_class


def test_service_migrates_legacy_txt_on_construction(tmp_path, monkeypatch) -> None:
    legacy_path = tmp_path / "live_queue.txt"
    legacy_path.write_text("1080playlists|https://youtube.com/watch?v=legacy\n")
    pending_path = tmp_path / "pending_queue.json"
    monkeypatch.setattr(download_service, "LIVE_QUEUE_FILE", legacy_path)
    monkeypatch.setattr(download_service, "PENDING_QUEUE_FILE", pending_path)

    service = make_service()

    records = load_pending_queue(service.pending_queue_path)
    assert {r["url"] for r in records} == {"https://youtube.com/watch?v=legacy"}
    assert not legacy_path.exists()
    assert legacy_path.with_suffix(".txt.migrated").exists()
