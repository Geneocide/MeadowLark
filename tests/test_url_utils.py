from src.url_utils import extract_playlist_id


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
