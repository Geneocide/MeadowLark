import pytest

from src.url_utils import extract_playlist_id, extract_video_id

# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=a&v=b", "a"),  # first value wins
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=xyz", "dQw4w9WgXcQ"),  # extra query ignored
    ],
)
def test_extract_video_id_valid(url: str, expected: str) -> None:
    assert extract_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "https://www.youtube.com/playlist?list=PLabc",  # no v param
        "https://www.youtube.com/watch?v=",  # empty v param
        "https://youtu.be/",  # bare slash, no id
        "https://example.com/watch?v=dQw4w9WgXcQ",  # wrong domain
        "not a url at all",
    ],
)
def test_extract_video_id_returns_none(url: str | None) -> None:
    assert extract_video_id(url) is None


def test_extract_video_id_youtu_be_extra_path_segment() -> None:
    # Extra path segments after the ID must not be included.
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ/extra") == "dQw4w9WgXcQ"


# ---------------------------------------------------------------------------
# extract_playlist_id
# ---------------------------------------------------------------------------


def test_extracts_list_param() -> None:
    url = "https://www.youtube.com/playlist?list=PLabc123"
    assert extract_playlist_id(url) == "PLabc123"


def test_returns_none_for_no_list_param() -> None:
    url = "https://www.youtube.com/watch?v=abc123"
    assert extract_playlist_id(url) is None


def test_returns_none_for_empty_string() -> None:
    assert extract_playlist_id("") is None


def test_returns_none_for_malformed_url() -> None:
    assert extract_playlist_id("not a url at all") is None


def test_handles_url_with_multiple_params() -> None:
    url = "https://www.youtube.com/watch?v=abc&list=PLxyz&index=1"
    assert extract_playlist_id(url) == "PLxyz"


def test_returns_none_for_none_input() -> None:
    assert extract_playlist_id(None) is None  # type: ignore[arg-type]


def test_returns_none_for_integer_input() -> None:
    assert extract_playlist_id(123) is None  # type: ignore[arg-type]
