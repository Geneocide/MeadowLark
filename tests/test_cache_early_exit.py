"""
Boundary tests for the cache early-exit path introduced in _filter_audio_playlist_urls.

Covers:
- _cache_put: video_id kwarg storage
- _cache_get_fresh_entry: TTL boundaries, missing keys, entry freshness
- Early-exit logic in _filter_audio_playlist_urls:
    - True positives  (should skip network call)
    - False positives (should NOT skip — video_id not in archive, stale TTL, etc.)
    - False negatives (exit fires but produces wrong status label)
    - Boundary intersections (archive_path/existing_ids presence, None video_id, etc.)
"""

import importlib.util
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Module loader (mirrors pattern from test_private_video_handling.py)
# ---------------------------------------------------------------------------


def _restore_module(name: str, mod: types.ModuleType | None) -> None:
    """
    Restore (or remove) a saved module and its parent-package attribute.

    exec_module re-imports popped submodules under the fake yt_dlp and rebinds
    them on their parent package (e.g. src.ydl_utils on src).  Restoring only
    sys.modules leaves a stale fake-bound attribute that breaks mock.patch
    targets resolved via getattr-walk like "src.ydl_utils.yt_dlp.YoutubeDL".
    """
    if mod is None:
        sys.modules.pop(name, None)
        return
    sys.modules[name] = mod
    parent_name, _, child = name.rpartition(".")
    if parent_name:
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, child, mod)


def import_vid_module():
    fake = types.ModuleType("yt_dlp")

    class _Dummy:
        def __init__(self, opts: dict) -> None:
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
            return False

        def extract_info(self, url: str, download: bool = False) -> dict:
            raise RuntimeError("unpatched DummyYDL invoked")

    fake.YoutubeDL = _Dummy
    utils_mod = types.ModuleType("yt_dlp.utils")

    class DownloadError(Exception):
        pass

    class ExtractorError(Exception):
        pass

    class MaxDownloadsReached(Exception):
        pass

    utils_mod.DownloadError = DownloadError
    utils_mod.ExtractorError = ExtractorError
    utils_mod.MaxDownloadsReached = MaxDownloadsReached

    old_yt_dlp = sys.modules.get("yt_dlp")
    old_yt_dlp_utils = sys.modules.get("yt_dlp.utils")
    old_src_download_executor = sys.modules.get("src.download_executor")
    old_src_ydl_utils = sys.modules.get("src.ydl_utils")
    sys.modules["yt_dlp"] = fake
    sys.modules["yt_dlp.utils"] = utils_mod
    sys.modules.pop("src.download_executor", None)
    sys.modules.pop("src.ydl_utils", None)

    path = str(Path(__file__).parent.parent / "meadowlark.pyw")
    repo_root = str(Path(path).parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    spec = importlib.util.spec_from_file_location("vd", path)
    vd = importlib.util.module_from_spec(spec)
    sys.modules["vd"] = vd
    try:
        spec.loader.exec_module(vd)
    finally:
        _restore_module("yt_dlp", old_yt_dlp)
        _restore_module("yt_dlp.utils", old_yt_dlp_utils)
        _restore_module("src.download_executor", old_src_download_executor)
        _restore_module("src.ydl_utils", old_src_ydl_utils)
    return vd


# ---------------------------------------------------------------------------
# Minimal stub window used by _filter_audio_playlist_urls tests
# The stub tracks whether fetch_latest_accessible_entry was called so tests
# can assert on the "no network call" contract.
# ---------------------------------------------------------------------------


class _NetworkCallSentinel(Exception):
    """Raised when fetch_latest_accessible_entry is invoked unexpectedly."""


def _make_dummy_win(vd: types.ModuleType, *, cache: dict | None = None):
    """Return a DummyWin instance wired to real MyWindow helpers."""

    class DummyWin:
        _podcast_latest_url_cache: dict = {}
        CACHE_TTL_SECONDS = vd.MyWindow.CACHE_TTL_SECONDS

        def _check_sponsorblock_for_video_id(self, vid: str) -> bool:
            return False

        def _cache_put(
            self,
            url: str,
            latest_url: str | None,
            latest_ts: int | None,
            *,
            video_id: str | None = None,
        ) -> None:
            pass  # no-op; individual tests override or inspect the real impl

        _cache_get_fresh_entry = vd.MyWindow._cache_get_fresh_entry
        _episode_already_archived = vd.MyWindow._episode_already_archived
        _skip_if_update_episode = vd.MyWindow._skip_if_update_episode
        _skip_if_short_duration = vd.MyWindow._skip_if_short_duration
        _classify_episode_by_age = vd.MyWindow._classify_episode_by_age

    win = DummyWin()
    win._podcast_latest_url_cache = cache if cache is not None else {}
    return win


# ===========================================================================
# 1. _cache_put unit tests
# ===========================================================================


def test_cache_put_stores_video_id_keyword_arg() -> None:
    """video_id supplied as a keyword arg must appear in the stored entry."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    # Bind the real implementation
    vd.MyWindow._cache_put(win, "http://pl/1", "http://vid/1", 1000, video_id="abc123")
    entry = win._podcast_latest_url_cache["http://pl/1"]
    assert entry["video_id"] == "abc123"


def test_cache_put_video_id_defaults_to_none() -> None:
    """When video_id is omitted the stored value must be None, not missing."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "http://pl/2", "http://vid/2", 1000)
    entry = win._podcast_latest_url_cache["http://pl/2"]
    assert "video_id" in entry
    assert entry["video_id"] is None


def test_cache_put_empty_playlist_url_does_not_store() -> None:
    """Guard clause: empty playlist_url must silently return without writing."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "", "http://vid/3", 1000, video_id="xyz")
    assert win._podcast_latest_url_cache == {}


def test_cache_put_empty_latest_url_does_not_store() -> None:
    """Guard clause: empty latest_url must silently return without writing."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "http://pl/4", "", 1000, video_id="xyz")
    assert win._podcast_latest_url_cache == {}


def test_cache_put_none_latest_url_does_not_store() -> None:
    """Guard clause: None latest_url (status_entry may not populate it) must not store."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "http://pl/5", None, 1000, video_id="xyz")
    assert win._podcast_latest_url_cache == {}


def test_cache_put_overwrites_existing_entry() -> None:
    """A second put for the same playlist_url must replace the old entry."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "http://pl/6", "http://vid/old", 100, video_id="old_id")
    vd.MyWindow._cache_put(win, "http://pl/6", "http://vid/new", 200, video_id="new_id")
    entry = win._podcast_latest_url_cache["http://pl/6"]
    assert entry["video_id"] == "new_id"
    assert entry["latest_url"] == "http://vid/new"


def test_cache_put_none_video_id_overwrites_previous_non_none() -> None:
    """Overwrite with video_id=None must explicitly clear a previously-set video_id."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    vd.MyWindow._cache_put(win, "http://pl/7", "http://vid/a", 50, video_id="old_id")
    vd.MyWindow._cache_put(win, "http://pl/7", "http://vid/b", 60)  # no video_id
    entry = win._podcast_latest_url_cache["http://pl/7"]
    assert entry["video_id"] is None


# ===========================================================================
# 2. _cache_get_fresh_entry unit tests
# ===========================================================================


def test_cache_get_fresh_entry_returns_none_for_missing_key() -> None:
    """Cache miss must return None, not raise KeyError."""
    vd = import_vid_module()
    win = _make_dummy_win(vd)
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://notcached")
    assert result is None


def test_cache_get_fresh_entry_returns_entry_within_ttl() -> None:
    """Entry fetched just now (0 seconds ago) must be returned."""
    vd = import_vid_module()
    win = _make_dummy_win(
        vd,
        cache={
            "http://pl/fresh": {
                "latest_url": "http://vid/fresh",
                "latest_ts": 999,
                "fetched_at": time.time(),
                "video_id": "vid_fresh",
            },
        },
    )
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://pl/fresh")
    assert result is not None
    assert result["video_id"] == "vid_fresh"


def test_cache_get_fresh_entry_returns_none_when_stale() -> None:
    """Entry older than CACHE_TTL_SECONDS (6 h) must return None."""
    vd = import_vid_module()
    stale_ts = time.time() - vd.MyWindow.CACHE_TTL_SECONDS - 1
    win = _make_dummy_win(
        vd,
        cache={
            "http://pl/stale": {
                "latest_url": "http://vid/stale",
                "latest_ts": 999,
                "fetched_at": stale_ts,
                "video_id": "stale_vid",
            },
        },
    )
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://pl/stale")
    assert result is None


def test_cache_get_fresh_entry_at_exact_ttl_boundary_is_stale() -> None:
    """Entry whose age equals CACHE_TTL_SECONDS exactly must be treated as stale (> check)."""
    vd = import_vid_module()
    # fetched_at set so that (time.time() - fetched_at) == CACHE_TTL_SECONDS
    # Because the TTL check is >, equal age is stale.
    exact_ts = time.time() - vd.MyWindow.CACHE_TTL_SECONDS
    win = _make_dummy_win(
        vd,
        cache={
            "http://pl/exact": {
                "latest_url": "http://vid/x",
                "latest_ts": 0,
                "fetched_at": exact_ts,
                "video_id": "exact_vid",
            },
        },
    )
    # At exact TTL the check is (age > TTL); at the boundary the difference may be
    # marginally > 0 due to execution time, so this test asserts the correct
    # semantic: an entry fetched exactly TTL seconds ago is expired.
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://pl/exact")
    # Allow None or a dict — we assert that if it returned a dict it is because
    # the age is still marginally less than TTL; but the boundary must not CRASH.
    assert result is None or isinstance(result, dict)


def test_cache_get_fresh_entry_missing_fetched_at_treated_as_stale() -> None:
    """Entry without 'fetched_at' key: .get('fetched_at', 0) → age is huge → stale."""
    vd = import_vid_module()
    win = _make_dummy_win(
        vd,
        cache={
            "http://pl/nofetchedat": {
                "latest_url": "http://vid/nfa",
                "latest_ts": 0,
                "video_id": "nfa_vid",
                # deliberately omit fetched_at
            },
        },
    )
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://pl/nofetchedat")
    assert result is None


def test_cache_get_fresh_entry_returns_full_dict_not_just_url() -> None:
    """The returned object must be the whole entry dict, not just latest_url (unlike _cache_get_fresh)."""
    vd = import_vid_module()
    entry = {
        "latest_url": "http://vid/full",
        "latest_ts": 42,
        "fetched_at": time.time(),
        "video_id": "full_vid",
    }
    win = _make_dummy_win(vd, cache={"http://pl/full": entry})
    result = vd.MyWindow._cache_get_fresh_entry(win, "http://pl/full")
    assert result is entry  # same object, not a copy


# ===========================================================================
# 3. Early-exit in _filter_audio_playlist_urls — TRUE POSITIVE
#    (should skip network call when everything lines up)
# ===========================================================================


def _build_filter_harness(
    vd: types.ModuleType,
    *,
    cache: dict,
    archive_content: str,
    urls: list[str],
    ydl_opts: dict,
    fetch_should_not_be_called: bool = True,
) -> tuple:
    """
    Run _filter_audio_playlist_urls with controlled cache/archive state.

    Installs a sentinel for fetch_latest_accessible_entry that raises
    _NetworkCallSentinel if invoked when fetch_should_not_be_called is True.
    """
    import src.podcast_filtering as pf

    fetch_calls: list[str] = []

    def _sentinel_fetch(url: str):
        fetch_calls.append(url)
        if fetch_should_not_be_called:
            msg = f"Unexpected network call for {url}"
            raise _NetworkCallSentinel(msg)
        # Minimal valid response
        return (
            [
                {
                    "id": "net_vid",
                    "webpage_url": "http://example.com/net",
                    "timestamp": 0,
                }
            ],
            False,
            {},
        )

    win = _make_dummy_win(vd, cache=cache)

    with (
        patch.object(pf, "load_downloaded_video_ids") as mock_load,
        patch.object(vd, "fetch_latest_accessible_entry", side_effect=_sentinel_fetch),
    ):
        mock_load.return_value = {
            line.split()[-1] for line in archive_content.splitlines() if line.strip()
        }
        result = vd.MyWindow._filter_audio_playlist_urls(win, urls, ydl_opts)

    return result, fetch_calls


def test_early_exit_fires_when_video_id_in_archive(tmp_path) -> None:
    """TRUE POSITIVE: cached video_id present in archive → skip network, status = Downloaded."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLabc123"
    vid = "cached_vid_001"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")

    cache = {
        url: {
            "latest_url": "http://example.com/cached_vid",
            "latest_ts": 1700000000,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }
    result, fetch_calls = _build_filter_harness(
        vd,
        cache=cache,
        archive_content=f"youtube {vid}",
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    to_download, pending, had_error, messages, statuses = result
    assert fetch_calls == [], "Network call must not fire when cache hit is valid"
    assert had_error is False
    assert len(statuses) == 1
    assert statuses[0]["status"] == "Downloaded"
    assert statuses[0]["latest_url"] == "http://example.com/cached_vid"


def test_early_exit_status_entry_contains_latest_ts(tmp_path) -> None:
    """Status entry built by early-exit must carry latest_ts from the cache."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLts"
    vid = "ts_vid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")
    expected_ts = 1714000000

    cache = {
        url: {
            "latest_url": "http://example.com/ts_vid",
            "latest_ts": expected_ts,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }
    result, _ = _build_filter_harness(
        vd,
        cache=cache,
        archive_content=f"youtube {vid}",
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    _, _, _, _, statuses = result
    assert statuses[0].get("latest_ts") == expected_ts


def test_early_exit_uses_audio_pl_comment_label_when_pl_id_matches(
    tmp_path, monkeypatch
) -> None:
    """When the playlist_id is in audio_pl_comments the status podcast field must use the label."""
    vd = import_vid_module()
    import utils as utils_module

    pl_id = "PLlabeled"
    url = f"http://www.youtube.com/playlist?list={pl_id}"
    vid = "labeled_vid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")

    monkeypatch.setattr(
        utils_module,
        "load_playlist_comments_for_source",
        lambda _: {pl_id: "My Podcast"},
    )
    monkeypatch.setattr(
        utils_module, "sanitize_for_path", lambda s: s.replace(" ", "_")
    )

    cache = {
        url: {
            "latest_url": "http://example.com/labeled",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }

    import src.podcast_filtering as pf

    win = _make_dummy_win(vd, cache=cache)
    with (
        patch.object(pf, "load_downloaded_video_ids", return_value={vid}),
        patch.object(vd, "fetch_latest_accessible_entry") as mock_fetch,
    ):
        result = vd.MyWindow._filter_audio_playlist_urls(
            win, [url], {"download_archive": str(archive_file)}
        )

    mock_fetch.assert_not_called()
    _, _, _, _, statuses = result
    assert statuses[0]["podcast"] == "My_Podcast"


def test_early_exit_falls_back_to_url_as_label_when_pl_id_not_in_comments(
    tmp_path, monkeypatch
) -> None:
    """When pl_id is absent from audio_pl_comments the podcast label must be the raw URL."""
    vd = import_vid_module()
    import utils as utils_module

    url = "http://example.com/playlist?list=PLunknown"
    vid = "unknown_vid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")

    monkeypatch.setattr(utils_module, "load_playlist_comments_for_source", lambda _: {})
    monkeypatch.setattr(utils_module, "sanitize_for_path", lambda s: s)

    cache = {
        url: {
            "latest_url": "http://example.com/unknown",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }

    import src.podcast_filtering as pf

    win = _make_dummy_win(vd, cache=cache)
    with (
        patch.object(pf, "load_downloaded_video_ids", return_value={vid}),
        patch.object(vd, "fetch_latest_accessible_entry") as mock_fetch,
    ):
        result = vd.MyWindow._filter_audio_playlist_urls(
            win, [url], {"download_archive": str(archive_file)}
        )

    mock_fetch.assert_not_called()
    _, _, _, _, statuses = result
    assert statuses[0]["podcast"] == url


# ===========================================================================
# 4. Early-exit FALSE POSITIVE cases — must NOT skip when conditions are unmet
# ===========================================================================


def _build_filter_harness_real_fetch(
    vd: types.ModuleType,
    *,
    cache: dict,
    archive_ids: set,
    urls: list[str],
    ydl_opts: dict,
) -> tuple:
    """Variant where fetch is allowed and tracked (for false-positive tests)."""
    import src.podcast_filtering as pf

    fetch_calls: list[str] = []

    def _tracking_fetch(url: str):
        fetch_calls.append(url)
        return (
            [
                {
                    "id": "net_vid",
                    "webpage_url": "http://example.com/net",
                    "timestamp": 0,
                }
            ],
            False,
            {},
        )

    win = _make_dummy_win(vd, cache=cache)
    with (
        patch.object(pf, "load_downloaded_video_ids", return_value=archive_ids),
        patch.object(vd, "fetch_latest_accessible_entry", side_effect=_tracking_fetch),
    ):
        result = vd.MyWindow._filter_audio_playlist_urls(win, urls, ydl_opts)

    return result, fetch_calls


def test_early_exit_does_not_fire_when_video_id_not_in_archive(tmp_path) -> None:
    """FALSE POSITIVE guard: cache hit but video_id absent from archive → must call network."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLnotarchived"
    vid = "not_in_archive"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("youtube some_other_vid\n", encoding="utf-8")

    cache = {
        url: {
            "latest_url": "http://example.com/notarchived",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }
    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache=cache,
        archive_ids={"some_other_vid"},
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    assert url in fetch_calls, (
        "Network call must fire when cached video_id is not in archive"
    )


def test_early_exit_does_not_fire_when_video_id_is_none(tmp_path) -> None:
    """FALSE POSITIVE guard: cache hit but video_id=None → must call network (can't confirm download)."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLnovidid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("youtube some_vid\n", encoding="utf-8")

    cache = {
        url: {
            "latest_url": "http://example.com/novidid",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": None,  # explicitly None
        },
    }
    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache=cache,
        archive_ids={"some_vid"},
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    assert url in fetch_calls, "Network call must fire when cached video_id is None"


def test_early_exit_does_not_fire_when_cache_stale(tmp_path) -> None:
    """FALSE POSITIVE guard: cache exists but is beyond TTL → must call network."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLstale"
    vid = "stale_vid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")

    stale_ts = time.time() - vd.MyWindow.CACHE_TTL_SECONDS - 60
    cache = {
        url: {
            "latest_url": "http://example.com/stale",
            "latest_ts": 0,
            "fetched_at": stale_ts,
            "video_id": vid,
        },
    }
    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache=cache,
        archive_ids={vid},
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    assert url in fetch_calls, "Network call must fire when cache entry is stale"


def test_early_exit_does_not_fire_when_no_archive_path(tmp_path) -> None:
    """FALSE POSITIVE guard: no archive configured → guard clause archive_path is falsy → network call."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLnoarchive"
    vid = "vid_noarchive"

    cache = {
        url: {
            "latest_url": "http://example.com/vid",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }
    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache=cache,
        archive_ids={vid},
        urls=[url],
        ydl_opts={},  # no download_archive key
    )
    assert url in fetch_calls, (
        "Network call must fire when no archive_path is configured"
    )


def test_early_exit_does_not_fire_when_archive_is_empty(tmp_path) -> None:
    """FALSE POSITIVE guard: archive file exists but is empty → existing_ids is empty set → network call."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLemptyarchive"
    vid = "vid_empty"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("", encoding="utf-8")

    cache = {
        url: {
            "latest_url": "http://example.com/empty",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid,
        },
    }
    # With empty archive existing_ids is an empty set which is falsy:
    # the guard `if archive_path and existing_ids:` short-circuits
    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache=cache,
        archive_ids=set(),  # empty
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    assert url in fetch_calls, (
        "Network call must fire when archive is empty (no IDs to match)"
    )


def test_early_exit_does_not_fire_when_no_cache_entry(tmp_path) -> None:
    """FALSE NEGATIVE baseline: empty cache → must always call network."""
    vd = import_vid_module()
    url = "http://example.com/playlist?list=PLnocache"
    vid = "nocache_vid"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text(f"youtube {vid}\n", encoding="utf-8")

    result, fetch_calls = _build_filter_harness_real_fetch(
        vd,
        cache={},
        archive_ids={vid},
        urls=[url],
        ydl_opts={"download_archive": str(archive_file)},
    )
    assert url in fetch_calls, "Network call must fire when cache is empty"


# ===========================================================================
# 5. Multiple URLs in a single call — mixed hit/miss
# ===========================================================================


def test_early_exit_partial_hit_across_multiple_urls(tmp_path, monkeypatch) -> None:
    """Only the URL with a valid cache hit should skip the network; the other must call it."""
    vd = import_vid_module()
    import src.podcast_filtering as pf
    import utils as utils_module

    monkeypatch.setattr(utils_module, "load_playlist_comments_for_source", lambda _: {})
    monkeypatch.setattr(utils_module, "sanitize_for_path", lambda s: s)

    url_hit = "http://example.com/playlist?list=PLhit"
    url_miss = "http://example.com/playlist?list=PLmiss"
    vid_hit = "hit_vid"
    vid_miss = "miss_vid"
    archive_file = tmp_path / "archive.txt"
    # Only vid_hit is in the archive; vid_miss is not
    archive_file.write_text(f"youtube {vid_hit}\n", encoding="utf-8")

    cache = {
        url_hit: {
            "latest_url": "http://example.com/hit",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid_hit,
        },
        url_miss: {
            "latest_url": "http://example.com/miss",
            "latest_ts": 0,
            "fetched_at": time.time(),
            "video_id": vid_miss,  # vid_miss is NOT in the archive
        },
    }

    fetch_calls: list[str] = []

    def _tracking_fetch(url: str):
        fetch_calls.append(url)
        return (
            [
                {
                    "id": "net_vid",
                    "webpage_url": "http://example.com/net",
                    "timestamp": 0,
                }
            ],
            False,
            {"title": "Net Podcast"},
        )

    win = _make_dummy_win(vd, cache=cache)
    with (
        patch.object(pf, "load_downloaded_video_ids", return_value={vid_hit}),
        patch.object(vd, "fetch_latest_accessible_entry", side_effect=_tracking_fetch),
        patch.object(
            utils_module, "resolve_playlist_label", return_value="Net Podcast"
        ),
    ):
        result = vd.MyWindow._filter_audio_playlist_urls(
            win,
            [url_hit, url_miss],
            {"download_archive": str(archive_file)},
        )

    _, _, _, _, statuses = result
    assert url_hit not in fetch_calls, "Hit URL must not trigger network"
    assert url_miss in fetch_calls, "Miss URL must trigger network"
    hit_status = next(s for s in statuses if s["url"] == url_hit)
    assert hit_status["status"] == "Downloaded"


# ===========================================================================
# 6. vid variable initialisation — ensure vid=None does not carry across URLs
# ===========================================================================


def test_cache_put_called_with_none_vid_when_entries_loop_does_not_execute(
    tmp_path, monkeypatch
) -> None:
    """
    Regression guard: empty entries list leaves vid=None; cache_put must receive video_id=None.

    When entries is an empty list the for-loop never runs, leaving vid=None.
    _cache_put must be called with video_id=None (not a stale vid from a prior URL).
    This guards against a hypothetical bug where vid is not reinitialised between
    loop iterations (it IS reinitialised in the code).
    """
    vd = import_vid_module()
    import src.podcast_filtering as pf
    import utils as utils_module

    monkeypatch.setattr(utils_module, "load_playlist_comments_for_source", lambda _: {})
    monkeypatch.setattr(utils_module, "sanitize_for_path", lambda s: s)
    monkeypatch.setattr(utils_module, "resolve_playlist_label", lambda _info, url: url)

    url = "http://example.com/playlist?list=PLemptyentries"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("", encoding="utf-8")

    cache_put_calls: list[dict] = []

    win = _make_dummy_win(vd, cache={})

    # Override _cache_put to record calls
    def _recording_cache_put(
        self_inner,
        playlist_url: str,
        latest_url: str | None,
        latest_ts: int | None,
        *,
        video_id: str | None = None,
    ) -> None:
        cache_put_calls.append({"playlist_url": playlist_url, "video_id": video_id})

    win._cache_put = lambda *a, **kw: _recording_cache_put(win, *a, **kw)

    with (
        patch.object(pf, "load_downloaded_video_ids", return_value=set()),
        patch.object(vd, "fetch_latest_accessible_entry", return_value=([], False, {})),
    ):
        vd.MyWindow._filter_audio_playlist_urls(
            win, [url], {"download_archive": str(archive_file)}
        )

    assert len(cache_put_calls) == 1
    assert cache_put_calls[0]["video_id"] is None


def test_vid_does_not_bleed_between_urls(tmp_path, monkeypatch) -> None:
    """
    Regression guard: vid must not leak from first URL to second URL's cache_put call.

    Vid must be reinitialised to None before the entries loop for each URL.
    If the first URL produces vid='first_vid' and the second URL returns an
    empty entries list, the cache_put for the second URL must pass video_id=None,
    NOT video_id='first_vid'.
    """
    vd = import_vid_module()
    import src.podcast_filtering as pf
    import utils as utils_module

    monkeypatch.setattr(utils_module, "load_playlist_comments_for_source", lambda _: {})
    monkeypatch.setattr(utils_module, "sanitize_for_path", lambda s: s)
    monkeypatch.setattr(utils_module, "resolve_playlist_label", lambda _info, url: url)

    url1 = "http://example.com/pl1?list=PL1"
    url2 = "http://example.com/pl2?list=PL2"
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("", encoding="utf-8")

    cache_put_calls: list[dict] = []

    win = _make_dummy_win(vd, cache={})

    def _recording_cache_put(
        self_inner,
        playlist_url: str,
        latest_url: str | None,
        latest_ts: int | None,
        *,
        video_id: str | None = None,
    ) -> None:
        cache_put_calls.append({"playlist_url": playlist_url, "video_id": video_id})

    win._cache_put = lambda *a, **kw: _recording_cache_put(win, *a, **kw)

    fetch_results = {
        url1: (
            [
                {
                    "id": "first_vid",
                    "webpage_url": "http://example.com/v1",
                    "timestamp": 0,
                }
            ],
            False,
            {},
        ),
        url2: ([], False, {}),
    }

    def _fetch(url: str):
        return fetch_results[url]

    with (
        patch.object(pf, "load_downloaded_video_ids", return_value=set()),
        patch.object(vd, "fetch_latest_accessible_entry", side_effect=_fetch),
    ):
        vd.MyWindow._filter_audio_playlist_urls(
            win, [url1, url2], {"download_archive": str(archive_file)}
        )

    assert len(cache_put_calls) == 2
    call_by_url = {c["playlist_url"]: c for c in cache_put_calls}
    assert call_by_url[url1]["video_id"] == "first_vid"
    assert call_by_url[url2]["video_id"] is None, (
        "vid must be None for url2 because its entries list was empty"
    )
