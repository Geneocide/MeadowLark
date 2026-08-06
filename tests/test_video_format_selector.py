"""
Regression tests for ``_build_video_format_selector``.

The selectors are exercised against yt-dlp's real format-selection engine with
synthetic format tables, so the assertions capture actual selector semantics
rather than string shape.

Covers:
  - Letterboxed / ultrawide renditions (no format is exactly 1080 or 720 tall)
  - Split-stream-only sites (HLS video-only + audio-only, i.e. no muxed format)
  - Conventional 16:9 tables still resolve to the requested rung
  - Requested height above everything on offer still yields the best available
  - height=None (unconstrained) and the webm-native branch
"""

import pytest
import yt_dlp

from src.ydl_options import _build_video_format_selector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _video(format_id: str, width: int, height: int, tbr: int, ext: str = "mp4") -> dict:
    """Build a video-only rendition, as an HLS extractor reports one."""
    return {
        "format_id": format_id,
        "url": f"https://example.invalid/{format_id}.m3u8",
        "ext": ext,
        "width": width,
        "height": height,
        "tbr": tbr,
        "vcodec": "avc1.640029",
        "acodec": "none",
        "protocol": "m3u8_native",
    }


def _audio(format_id: str = "audio-English", ext: str = "m4a") -> dict:
    """Build an audio-only rendition."""
    return {
        "format_id": format_id,
        "url": f"https://example.invalid/{format_id}.m3u8",
        "ext": ext,
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "protocol": "m3u8_native",
    }


def _muxed(format_id: str, width: int, height: int, tbr: int) -> dict:
    """Build a progressive format carrying both streams."""
    return {
        "format_id": format_id,
        "url": f"https://example.invalid/{format_id}.mp4",
        "ext": "mp4",
        "width": width,
        "height": height,
        "tbr": tbr,
        "vcodec": "avc1.640029",
        "acodec": "mp4a.40.2",
        "protocol": "https",
    }


def _select(spec: str, formats: list[dict]) -> list[dict]:
    """
    Run ``spec`` through yt-dlp's selector engine; return the chosen formats.

    The formats are put through yt-dlp's own quality sort first, exactly as
    ``process_video_result`` does — the selector reads a list ordered
    worst-to-best, so skipping the sort would make results depend on fixture
    ordering rather than on the selector.
    """
    with yt_dlp.YoutubeDL({"quiet": True, "simulate": True}) as ydl:
        info = {"formats": [f.copy() for f in formats]}
        ydl.sort_formats(info)
        return ydl._select_formats(info["formats"], ydl.build_format_selector(spec))


def _heights(selected: list[dict]) -> set[int]:
    """Heights of the video streams in a selection, flattening merged results."""
    heights: set[int] = set()
    for fmt in selected:
        for part in fmt.get("requested_formats", [fmt]):
            if part.get("height"):
                heights.add(part["height"])
    return heights


# Nebula's rendition ladder for a 2.35:1 letterboxed video: nothing is exactly
# 1080 or 720 tall, and every stream is video-only or audio-only.
LETTERBOXED_SPLIT_FORMATS: list[dict] = [
    _audio(),
    _video("751", 640, 272, 752),
    _video("1332", 960, 408, 1332),
    _video("2706", 1280, 544, 2706),
    _video("5963", 1920, 816, 5963),
    _video("10175", 2560, 1088, 10175),
]

# A conventional 16:9 ladder, also split-stream.
WIDESCREEN_SPLIT_FORMATS: list[dict] = [
    _audio(),
    _video("360", 640, 360, 700),
    _video("720", 1280, 720, 2500),
    _video("1080", 1920, 1080, 5000),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "expected_height"),
    [(1080, 816), (720, 544), (2160, 1088), (480, 408)],
)
def test_letterboxed_ladder_resolves_to_tier_at_or_below_request(
    requested: int, expected_height: int
) -> None:
    """
    A quality rung names a tier, not a literal pixel height.

    Ultrawide masters are encoded at 1920x816, 1280x544, ...; an equality match
    on height selects nothing and fails the whole download.
    """
    spec = _build_video_format_selector(requested, "mp4")
    selected = _select(spec, LETTERBOXED_SPLIT_FORMATS)
    assert selected, f"no format matched {spec!r}"
    assert _heights(selected) == {expected_height}


def test_split_stream_only_site_below_smallest_rendition_still_selects() -> None:
    """
    The catch-all rung must fire on sites that publish no muxed format.

    Bare ``best`` only matches muxed formats, so it can never satisfy an
    HLS ladder of video-only + audio-only streams.
    """
    formats = [_audio(), _video("5963", 1920, 816, 5963)]
    selected = _select(_build_video_format_selector(720, "mp4"), formats)
    assert _heights(selected) == {816}


def test_muxed_only_site_below_smallest_rendition_still_selects() -> None:
    """The muxed catch-all is retained for progressive-only sites."""
    formats = [_muxed("hd", 1920, 1080, 4000)]
    selected = _select(_build_video_format_selector(720, "mp4"), formats)
    assert _heights(selected) == {1080}


@pytest.mark.parametrize("requested", [1080, 720, 360])
def test_widescreen_ladder_still_honours_exact_rung(requested: int) -> None:
    """Conventional 16:9 sources keep resolving to the requested height."""
    selected = _select(_build_video_format_selector(requested, "mp4"), WIDESCREEN_SPLIT_FORMATS)
    assert _heights(selected) == {requested}


def test_request_never_exceeds_ceiling_when_higher_tiers_exist() -> None:
    """A capped request must not silently upgrade past its ceiling."""
    selected = _select(_build_video_format_selector(720, "mp4"), LETTERBOXED_SPLIT_FORMATS)
    assert max(_heights(selected)) <= 720


def test_unconstrained_request_takes_the_best_rendition() -> None:
    """height=None means 'no ceiling'."""
    selected = _select(_build_video_format_selector(None, "mp4"), LETTERBOXED_SPLIT_FORMATS)
    assert _heights(selected) == {1088}


def test_webm_branch_matches_letterboxed_heights() -> None:
    """The webm-native branch has the same tier semantics, staying webm-only."""
    formats = [
        _audio("audio-webm", ext="webm"),
        _video("vp9-816", 1920, 816, 4000, ext="webm"),
        _video("vp9-544", 1280, 544, 2000, ext="webm"),
    ]
    selected = _select(_build_video_format_selector(1080, "webm"), formats)
    assert _heights(selected) == {816}


def test_webm_branch_falls_back_above_ceiling_rather_than_failing() -> None:
    """No webm at or below the ceiling: take the best webm rather than fail."""
    formats = [
        _audio("audio-webm", ext="webm"),
        _video("vp9-816", 1920, 816, 4000, ext="webm"),
    ]
    selected = _select(_build_video_format_selector(480, "webm"), formats)
    assert _heights(selected) == {816}
