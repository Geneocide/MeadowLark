"""Unit tests for src.ydl_options builders."""
# ruff: noqa: S101

from src.dict_utils import DEFAULT_POSTPROCESSORS
from src.ydl_options import get_output_template, get_postprocessors, get_source_options


def test_get_source_options_numeric_height_format() -> None:
    opts = get_source_options("480")
    assert "height=480" in opts["format"]


def test_get_source_options_non_numeric_fallback_format() -> None:
    opts = get_source_options("garbage")
    assert opts["format"] == "bestvideo*+bestaudio/best"


def test_get_source_options_unknown_returns_mp4_merge() -> None:
    opts = get_source_options("garbage")
    assert opts["merge_output_format"] == "mp4"


def test_get_output_template_audio_returns_outtmpl() -> None:
    template = get_output_template("audio")
    assert "%(title)s.%(ext)s" in template


def test_get_postprocessors_audio_returns_audio_postprocessors() -> None:
    postprocs = get_postprocessors("audio")
    keys = [pp.get("key") for pp in postprocs]
    assert "FFmpegExtractAudio" in keys


def test_get_postprocessors_no_postprocessors_key_falls_back_to_default() -> None:
    # "720playlists" has no "postprocessors" key → .get() returns DEFAULT_POSTPROCESSORS
    postprocs = get_postprocessors("720playlists")
    default_keys = {pp["key"] for pp in DEFAULT_POSTPROCESSORS}
    result_keys = {pp["key"] for pp in postprocs}
    assert default_keys == result_keys
