"""
Regression tests for the invariant that every podcast episode is filed under its show folder.

A podcast episode that is still live when the podcast check runs is skipped by
``build_match_filter`` and parked in the live queue.  When the stream ends the
episode is re-queued from the live queue, and that path must rebuild the same
``<podcast base>/<show label>/`` output template the grouped podcast download
used -- otherwise the episode lands in the "misc" directory that
``get_source_options("audio_playlists")`` points at.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import src.settings_dialog as sd
from src.live_queue import add_to_live_queue, load_live_queue, save_live_queue
from src.path_utils import sanitize_for_path
from src.ydl_options import build_podcast_outtmpl, podcast_base_dir
from tests.test_cache_early_exit import import_vid_module
from tests.test_live_queue import make_service

SHOW = "Android Faithful"


# ---------------------------------------------------------------------------
# Output-template helper
# ---------------------------------------------------------------------------


def test_build_podcast_outtmpl_uses_show_folder_beside_misc_dir() -> None:
    """The show folder is a sibling of the configured misc directory."""
    tmpl = build_podcast_outtmpl(SHOW)
    assert tmpl == f"{podcast_base_dir()}/{SHOW}/%(title)s.%(ext)s"


def test_build_podcast_outtmpl_falls_back_to_misc_for_unknown_show() -> None:
    """An episode with no resolvable show label still has a home."""
    assert build_podcast_outtmpl(None) == f"{podcast_base_dir()}/misc/%(title)s.%(ext)s"


def test_build_podcast_outtmpl_empty_string_label_falls_back_to_misc() -> None:
    """An empty-string label is falsy, same as None -- it must not create a folder named ''."""
    assert build_podcast_outtmpl("") == f"{podcast_base_dir()}/misc/%(title)s.%(ext)s"


def test_build_podcast_outtmpl_whitespace_only_label_falls_back_to_misc() -> None:
    """
    A whitespace-only label is truthy in Python.

    sanitize_for_path collapses it to '' internally, so it lands in misc too --
    via a different code path than None.
    """
    assert build_podcast_outtmpl("   ") == f"{podcast_base_dir()}/misc/%(title)s.%(ext)s"


def test_build_podcast_outtmpl_numeric_string_label_is_not_falsy() -> None:
    """A label of "0" is a non-empty string and must not be mistaken for missing (JS-style falsy trap)."""
    assert build_podcast_outtmpl("0") == f"{podcast_base_dir()}/0/%(title)s.%(ext)s"


def test_build_podcast_outtmpl_sanitizes_windows_invalid_chars() -> None:
    """Show names containing Windows-illegal path characters are sanitized, not passed through raw."""
    raw = 'Cool Show: "Live" <2024>|Ep?1*'
    expected_label = sanitize_for_path(raw)
    tmpl = build_podcast_outtmpl(raw)
    assert tmpl == f"{podcast_base_dir()}/{expected_label}/%(title)s.%(ext)s"
    label_segment = tmpl.split("/")[-2]
    for ch in '<>:"/\\|?*':
        assert ch not in label_segment


def test_build_podcast_outtmpl_slugifies_very_long_label() -> None:
    """
    A show label long enough to blow the Windows path budget gets slugified.

    It is replaced with a short hash-based slug rather than being written out in full.
    """
    with patch.dict(sd._runtime, {"VID_DL_PODCAST_MISC_OUTPUT_DIR": "/x/misc"}):
        long_label = "A" * 300
        tmpl = build_podcast_outtmpl(long_label)
    assert long_label not in tmpl
    label_segment = tmpl.split("/")[-2]
    assert len(label_segment) < 60


def test_build_podcast_outtmpl_uses_custom_misc_dir_override() -> None:
    """
    podcast_base_dir() and the misc fallback both track a runtime override.

    Not just the frozen config constant.
    """
    with patch.dict(sd._runtime, {"VID_DL_PODCAST_MISC_OUTPUT_DIR": "/custom/pods/misc"}):
        assert podcast_base_dir() == "/custom/pods"
        assert build_podcast_outtmpl(None) == "/custom/pods/misc/%(title)s.%(ext)s"
        assert build_podcast_outtmpl(SHOW) == f"/custom/pods/{SHOW}/%(title)s.%(ext)s"


# ---------------------------------------------------------------------------
# Live-queue persistence of the show label
# ---------------------------------------------------------------------------


def test_live_queue_round_trips_show_label(tmp_path: Path) -> None:
    """The show label survives the file round-trip so it can rebuild the outtmpl."""
    path = tmp_path / "live_queue.txt"
    entries = {"https://yt.com/watch?v=abc": ("audio_playlists", "PLxyz", SHOW)}
    save_live_queue(path, entries)
    assert load_live_queue(path) == entries


def test_live_queue_loads_legacy_lines_without_label(tmp_path: Path) -> None:
    """Entries written before the label field parse with label None."""
    path = tmp_path / "live_queue.txt"
    path.write_text("720playlists|https://yt.com/watch?v=abc|PLxyz\n", encoding="utf-8")
    assert load_live_queue(path) == {
        "https://yt.com/watch?v=abc": ("720playlists", "PLxyz", None),
    }


def test_add_to_live_queue_stores_label(tmp_path: Path) -> None:
    """The label passed at queue time is persisted with the entry."""
    path = tmp_path / "live_queue.txt"
    add_to_live_queue(path, "https://yt.com/watch?v=abc", "audio_playlists", None, SHOW)
    assert load_live_queue(path)["https://yt.com/watch?v=abc"] == (
        "audio_playlists",
        None,
        SHOW,
    )


# ---------------------------------------------------------------------------
# Re-queue from the live queue must restore the show folder
# ---------------------------------------------------------------------------


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.load_playlist_comments_for_source", return_value={})
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_restores_show_folder_for_podcast(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path: Path,
) -> None:
    """An ended podcast livestream is re-queued into its show folder, not misc."""
    path = tmp_path / "live_queue.txt"
    path.write_text(
        f"audio_playlists|https://youtube.com/watch?v=ended||{SHOW}\n",
        encoding="utf-8",
    )

    queue = MagicMock()
    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: MagicMock(info_changed=MagicMock()),
        qlogger_factory=lambda: MagicMock(message_changed=MagicMock()),
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"is_live": False, "live_status": None}
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    _urls, queued_opts = queue.put.call_args[0][0]
    assert queued_opts["outtmpl"] == build_podcast_outtmpl(SHOW)


@patch("src.download_service.yt_dlp.YoutubeDL")
@patch("src.download_service.utils.load_playlist_comments_for_source", return_value={})
@patch("src.download_service.utils.detect_site_from_urls", return_value="youtube")
@patch(
    "src.download_service.utils.build_base_ydl_opts",
    return_value={"logger": None, "progress_hooks": []},
)
def test_check_live_queue_leaves_video_outtmpl_untouched(
    mock_build_base,
    mock_detect_site,
    mock_load_comments,
    mock_ydl_class,
    tmp_path: Path,
) -> None:
    """Video sources keep their own %(playlist)s template; only podcasts are relabelled."""
    path = tmp_path / "live_queue.txt"
    path.write_text(
        "1080playlists|https://youtube.com/watch?v=ended\n",
        encoding="utf-8",
    )

    queue = MagicMock()
    service = make_service(
        download_queue=queue,
        qhook_factory=lambda: MagicMock(info_changed=MagicMock()),
        qlogger_factory=lambda: MagicMock(message_changed=MagicMock()),
        bar_progress_set_range_callback=Mock(),
        handle_info_changed_callback=Mock(),
        handle_log_entry_callback=Mock(),
    )
    service.live_queue_path = path

    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {"is_live": False, "live_status": None}
    mock_ydl_class.return_value.__enter__.return_value = mock_instance

    service.check_live_queue()

    _urls, queued_opts = queue.put.call_args[0][0]
    assert "%(playlist)s" in queued_opts["outtmpl"]


# ---------------------------------------------------------------------------
# The label reaches the live queue in the first place
# ---------------------------------------------------------------------------


def test_window_check_live_queue_restores_show_folder(tmp_path: Path) -> None:
    """MyWindow (the path the app actually runs) re-files an ended stream by label."""
    vd = import_vid_module()
    path = tmp_path / "live_queue.txt"
    path.write_text(
        f"audio_playlists|https://youtube.com/watch?v=ended||{SHOW}\n",
        encoding="utf-8",
    )

    queued: list = []

    class DummyWin:
        live_queue_path = path
        logEdit = SimpleNamespace(appendPlainText=lambda _msg: None)
        barProgress = SimpleNamespace(setRange=lambda _a, _b: None)
        downloadQueue = SimpleNamespace(put=queued.append)
        load_live_queue = vd.MyWindow.load_live_queue
        save_live_queue = vd.MyWindow.save_live_queue
        check_live_queue = vd.MyWindow.check_live_queue

        def _create_download_context(self):
            return (
                SimpleNamespace(info_changed=None),
                SimpleNamespace(message_changed=None),
                {},
            )

        def get_options(self, urls, source, skip_playlist_dialog=False):
            return dict(vd.utils.get_source_options(source))

        def append_properties(self, ydl_opts, properties):
            ydl_opts.update(properties)
            return ydl_opts

        def _wire_download_signals(self, _qhook, _qlogger) -> None:
            pass

    ydl = MagicMock()
    ydl.extract_info.return_value = {"is_live": False, "live_status": None}
    with patch.object(vd.yt_dlp, "YoutubeDL") as mock_ydl:
        mock_ydl.return_value.__enter__.return_value = ydl
        DummyWin().check_live_queue()

    (_urls, queued_opts) = queued[0]
    assert queued_opts["outtmpl"] == build_podcast_outtmpl(SHOW)


def test_grouped_podcast_batch_binds_show_label_to_match_filter(
    tmp_path: Path,
) -> None:
    """The batch filter parks a still-live episode with the batch's show label."""
    vd = import_vid_module()

    queued: list = []

    class DummyWin:
        live_queue_path = tmp_path / "live_queue.txt"
        live_queue_log = SimpleNamespace(emit=lambda _msg: None)
        downloadQueue = SimpleNamespace(put=queued.append)
        barProgress = SimpleNamespace(setRange=lambda _a, _b: None)
        add_to_live_queue = vd.MyWindow.add_to_live_queue
        make_match_filter = vd.MyWindow.make_match_filter
        _queue_podcast_downloads_grouped = vd.MyWindow._queue_podcast_downloads_grouped

        def _fork_download_context(self, base_opts: dict):
            return SimpleNamespace(info_changed=None), SimpleNamespace(
                message_changed=None
            ), dict(base_opts)

        def _wire_download_signals(self, _qhook, _qlogger) -> None:
            pass

    win = DummyWin()
    win._queue_podcast_downloads_grouped(
        [{"url": "https://youtube.com/watch?v=live", "playlist": SHOW}],
        {"match_filter": lambda _info, _incomplete: None},
    )

    (_urls, batch_opts) = queued[0]
    assert batch_opts["outtmpl"] == build_podcast_outtmpl(SHOW)

    batch_opts["match_filter"](
        {
            "is_live": True,
            "live_status": "is_live",
            "webpage_url": "https://youtube.com/watch?v=live",
        },
        False,
    )
    assert load_live_queue(DummyWin.live_queue_path)[
        "https://youtube.com/watch?v=live"
    ] == ("audio_playlists", None, SHOW)


def test_match_filter_records_show_label_for_live_episode(tmp_path: Path) -> None:
    """A live podcast episode is parked in the queue together with its show label."""
    path = tmp_path / "live_queue.txt"
    service = make_service()
    service.live_queue_path = path
    service.add_to_live_queue_callback = service.add_to_live_queue

    match_filter = service.make_match_filter("audio_playlists", label=SHOW)
    match_filter(
        {
            "is_live": True,
            "live_status": "is_live",
            "webpage_url": "https://youtube.com/watch?v=live",
        },
        False,
    )

    assert load_live_queue(path)["https://youtube.com/watch?v=live"] == (
        "audio_playlists",
        None,
        SHOW,
    )
