import importlib.util
import sys

# helper function to import the main module even though its filename contains a space
import types

import pytest


def import_vid_module():
    # before loading the target module, provide a minimal fake yt_dlp so the
    # import statement inside the file succeeds.  Individual tests will
    # monkeypatch ``YoutubeDL`` on the imported module as needed.
    fake = types.ModuleType("yt_dlp")

    # a dummy context manager; methods will be replaced by tests via monkeypatch
    class _Dummy:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            raise RuntimeError("unpatched DummyYDL invoked")

    fake.YoutubeDL = _Dummy
    # also provide a minimal ``yt_dlp.utils`` namespace so imports in QYT.py succeed
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
    sys.modules["yt_dlp"] = fake
    sys.modules["yt_dlp.utils"] = utils_mod

    path = r"c:\Users\etreq\dev\vid downloader\vid downloader.pyw"
    spec = importlib.util.spec_from_file_location("vd", path)
    vd = importlib.util.module_from_spec(spec)
    sys.modules["vd"] = vd
    spec.loader.exec_module(vd)
    return vd


def test_fetch_latest_accessible_entry_skips_private(monkeypatch):
    vd = import_vid_module()

    class DummyYDL:
        call_count = 0

        def __init__(self, opts):
            DummyYDL.call_count += 1
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            # first invocation simulates private-latest behaviour
            if self.opts.get("playlistend") == 1:
                raise Exception("Private video is not available")
            # fallback returns a normal entry
            return {
                "entries": [
                    {
                        "title": "Accessible episode",
                        "id": "abc123",
                        "webpage_url": "http://example.com/accessible",
                    },
                ],
            }

    monkeypatch.setattr(vd.yt_dlp, "YoutubeDL", DummyYDL)
    entries, skipped, info = vd._fetch_latest_accessible_entry("http://fake-playlist")
    assert skipped is True
    assert isinstance(entries, list) and len(entries) == 1
    assert entries[0]["webpage_url"] == "http://example.com/accessible"
    # info should be the original dictionary returned by the dummy
    assert isinstance(info, dict)
    # because the first attempt failed, we should have made two calls
    assert DummyYDL.call_count == 2


def test_fetch_latest_accessible_entry_two_private_then_good(monkeypatch):
    vd = import_vid_module()

    class DummyYDL2:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            n = self.opts.get("playlistend")
            if n in (1, 2):
                # pretend the last entry is private
                return {"entries": [{"title": "Private video foo"}]}
            return {
                "entries": [
                    {
                        "title": "Working",
                        "id": "good",
                        "webpage_url": "http://example.com/good3",
                    },
                ],
                "title": "Playlist",
            }

    monkeypatch.setattr(vd.yt_dlp, "YoutubeDL", DummyYDL2)
    entries, skipped, info = vd._fetch_latest_accessible_entry("http://fake3")
    assert skipped is True
    assert entries[0]["webpage_url"] == "http://example.com/good3"
    assert info.get("title") == "Playlist"


def test_fetch_latest_accessible_entry_private_by_title(monkeypatch):
    vd = import_vid_module()

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            if self.opts.get("playlistend") == 1:
                # return an entry whose title begins with the magic phrase
                return {"entries": [{"title": "Private video #456"}]}
            return {
                "entries": [
                    {
                        "title": "Other",
                        "id": "xyz",
                        "webpage_url": "http://example.com/other",
                    },
                ],
            }

    monkeypatch.setattr(vd.yt_dlp, "YoutubeDL", DummyYDL)
    entries, skipped, info = vd._fetch_latest_accessible_entry("http://fake2")
    assert skipped is True
    assert entries[0]["webpage_url"] == "http://example.com/other"


def test_filter_audio_playlist_urls_with_private(monkeypatch):
    # we don't need a real GUI instance; just supply an object with the
    # attributes that ``_filter_audio_playlist_urls`` touches.
    vd = import_vid_module()

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            if self.opts.get("playlistend") == 1:
                raise Exception("Private video is not available")
            return {
                "entries": [
                    {
                        "title": "Good episode",
                        "id": "id123",
                        "webpage_url": "http://example.com/good",
                    },
                ],
            }

    monkeypatch.setattr(vd.yt_dlp, "YoutubeDL", DummyYDL)

    # use dummy window-like object
    class DummyWin:
        def _check_sponsorblock_for_video_id(self, vid):
            return False

        def _cache_put(self, url, latest_url, ts):
            pass

    win = DummyWin()
    to_download, pending, had_error, messages, statuses = (
        vd.MyWindow._filter_audio_playlist_urls(
            win,
            ["http://fake-playlist"],
            {},
        )
    )
    assert had_error is False
    assert any("private" in m.lower() for m in messages)
    assert statuses[0]["latest_url"] == "http://example.com/good"


def test_fetch_latest_accessible_entry_no_accessible(monkeypatch):
    vd = import_vid_module()

    class DummyYDL2:
        call_count = 0

        def __init__(self, opts):
            DummyYDL2.call_count += 1
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download=False):
            # always claim private
            if self.opts.get("playlistend") == 1:
                raise Exception("Private video")
            return {
                "entries": [{"title": "Private video 1"}, {"title": "Private video 2"}],
            }

    monkeypatch.setattr(vd.yt_dlp, "YoutubeDL", DummyYDL2)
    with pytest.raises(Exception) as excinfo:
        vd._fetch_latest_accessible_entry("http://nothing")
    assert "Private video" in str(excinfo.value)
    # should have retried up to the lookup limit
    # the dummy is called once per lookahead attempt
    assert DummyYDL2.call_count == vd.MAX_LOOKAHEAD
