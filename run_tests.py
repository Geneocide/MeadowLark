"""Manual test runner for Phase 1.5 tests."""

import sys

from src.dict_utils import merge_dicts_recursive, remove_sponsorblock_postprocessor
from src.path_utils import (
    resolve_playlist_label,
    sanitize_for_path,
    slugify_if_too_long,
)
from src.playlist_utils import detect_site_from_urls, is_primitive_technology
from src.version_utils import normalize_version


class TestRunner:
    """Simple test runner."""

    def __init__(self) -> None:
        """Initialize test runner."""
        self.passed = 0
        self.failed = 0

    def run_test(self, test_func: callable, test_name: str) -> None:
        """Run a single test."""
        try:
            test_func()
            print(f"✓ {test_name}")
            self.passed += 1
        except (AssertionError, AttributeError, TypeError, ValueError) as e:
            print(f"✗ {test_name}")
            print(f"  Error: {e}")
            self.failed += 1

    def report(self) -> None:
        """Report results."""
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"Tests passed: {self.passed}/{total}")
        if self.failed > 0:
            print(f"Tests failed: {self.failed}")
            sys.exit(1)
        else:
            print("All tests passed!")


# Test cases
runner = TestRunner()


def test_normalize_version_valid() -> None:
    """Test normalize_version with valid version strings."""
    assert normalize_version("2025.08.27") == (2025, 8, 27)
    assert normalize_version("2025.8.27") == (2025, 8, 27)
    assert normalize_version("1.0.0") == (1, 0, 0)


def test_normalize_version_invalid() -> None:
    """Test normalize_version with invalid inputs."""
    assert normalize_version(None) == ()  # type: ignore
    assert normalize_version("") == ()
    assert normalize_version("abc") == ()


def test_merge_dicts_recursive_basic() -> None:
    """Test basic dictionary merging."""
    base = {"a": 1, "b": 2}
    overrides = {"b": 3, "c": 4}
    result = merge_dicts_recursive(base, overrides)
    assert result == {"a": 1, "b": 3, "c": 4}


def test_merge_dicts_recursive_nested() -> None:
    """Test nested dictionary merging."""
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    overrides = {"a": {"y": 20, "z": 30}}
    result = merge_dicts_recursive(base, overrides)
    assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}


def test_merge_dicts_recursive_preserves_input() -> None:
    """Test that merge doesn't mutate input dictionaries."""
    base = {"a": 1}
    overrides = {"b": 2}
    merge_dicts_recursive(base, overrides)
    assert base == {"a": 1}
    assert overrides == {"b": 2}


def test_merge_dicts_recursive_lists() -> None:
    """Test list merging in dictionaries."""
    base = {"items": [1, 2]}
    overrides = {"items": [3, 4]}
    result = merge_dicts_recursive(base, overrides)
    assert result == {"items": [1, 2, 3, 4]}


def test_remove_sponsorblock_postprocessor() -> None:
    """Test SponsorBlock postprocessor removal."""
    opts = {
        "postprocessors": [
            {"key": "SponsorBlock"},
            {"key": "FFmpegExtractAudio"},
        ],
    }
    result = remove_sponsorblock_postprocessor(opts)
    assert len(result["postprocessors"]) == 1
    assert result["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    # Verify original not mutated
    assert len(opts["postprocessors"]) == 2


def test_detect_site_from_urls_youtube() -> None:
    """Test YouTube site detection."""
    assert detect_site_from_urls(["https://youtube.com/watch?v=123"]) == "youtube"
    assert detect_site_from_urls(["https://youtu.be/123"]) == "youtube"


def test_detect_site_from_urls_nebula() -> None:
    """Test Nebula site detection."""
    assert detect_site_from_urls(["https://watchnebula.com/video"]) == "nebula"


def test_detect_site_from_urls_unknown() -> None:
    """Test unknown site detection."""
    assert detect_site_from_urls(["https://example.com"]) == "unknown"
    assert detect_site_from_urls([]) == "unknown"


def test_is_primitive_technology_channel() -> None:
    """Test Primitive Technology channel detection."""
    assert is_primitive_technology({"channel": "Primitive Technology"})
    assert is_primitive_technology({"uploader": "Primitive Technology"})


def test_is_primitive_technology_title() -> None:
    """Test Primitive Technology title prefix detection."""
    assert is_primitive_technology({"title": "Primitive Technology: Building"})


def test_is_primitive_technology_not() -> None:
    """Test non-Primitive Technology detection."""
    assert not is_primitive_technology({"channel": "Other Channel"})
    assert not is_primitive_technology({})


def test_sanitize_for_path_removes_invalid() -> None:
    """Test invalid character removal."""
    assert sanitize_for_path("my<file>") == "my_file_"
    assert sanitize_for_path('my"folder"') == "my_folder_"


def test_sanitize_for_path_empty() -> None:
    """Test empty input handling."""
    assert sanitize_for_path("") == "misc"
    assert sanitize_for_path("   ") == "misc"


def test_sanitize_for_path_preserves_valid() -> None:
    """Test valid characters are preserved."""
    assert sanitize_for_path("my_folder-123") == "my_folder-123"
    assert sanitize_for_path("My Folder123") == "My Folder123"


def test_slugify_if_too_long_short_path() -> None:
    """Test slugify with short path."""
    result = slugify_if_too_long("/base", "label")
    assert result == "label"


def test_slugify_if_too_long_long_path() -> None:
    """Test slugify with very long path."""
    long_label = "a" * 200
    result = slugify_if_too_long("/base", long_label, max_total=50)
    assert len(result) < len(long_label)


def test_resolve_playlist_label_from_title() -> None:
    """Test label resolution from title."""
    info = {"title": "My Playlist"}
    assert resolve_playlist_label(info, "url") == "My Playlist"


def test_resolve_playlist_label_fallback() -> None:
    """Test label resolution fallback."""
    info = {}
    result = resolve_playlist_label(info, "https://example.com/path")
    assert isinstance(result, str)
    assert len(result) > 0


# Run all tests
if __name__ == "__main__":
    tests = [
        (test_normalize_version_valid, "normalize_version: valid strings"),
        (test_normalize_version_invalid, "normalize_version: invalid inputs"),
        (test_merge_dicts_recursive_basic, "merge_dicts_recursive: basic merge"),
        (test_merge_dicts_recursive_nested, "merge_dicts_recursive: nested merge"),
        (
            test_merge_dicts_recursive_preserves_input,
            "merge_dicts_recursive: preserves input",
        ),
        (test_merge_dicts_recursive_lists, "merge_dicts_recursive: list merging"),
        (test_remove_sponsorblock_postprocessor, "remove_sponsorblock_postprocessor"),
        (test_detect_site_from_urls_youtube, "detect_site_from_urls: youtube"),
        (test_detect_site_from_urls_nebula, "detect_site_from_urls: nebula"),
        (test_detect_site_from_urls_unknown, "detect_site_from_urls: unknown"),
        (test_is_primitive_technology_channel, "is_primitive_technology: channel"),
        (test_is_primitive_technology_title, "is_primitive_technology: title"),
        (test_is_primitive_technology_not, "is_primitive_technology: not detected"),
        (test_sanitize_for_path_removes_invalid, "sanitize_for_path: removes invalid"),
        (test_sanitize_for_path_empty, "sanitize_for_path: empty input"),
        (test_sanitize_for_path_preserves_valid, "sanitize_for_path: preserves valid"),
        (test_slugify_if_too_long_short_path, "slugify_if_too_long: short path"),
        (test_slugify_if_too_long_long_path, "slugify_if_too_long: long path"),
        (test_resolve_playlist_label_from_title, "resolve_playlist_label: from title"),
        (test_resolve_playlist_label_fallback, "resolve_playlist_label: fallback"),
    ]

    for test_func, test_name in tests:
        runner.run_test(test_func, test_name)

    runner.report()
