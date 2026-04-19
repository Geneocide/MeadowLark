"""Tests for history dialog filter logic."""
# ruff: noqa: S101

from src.history_dialog import _result_matches


class TestResultMatches:
    """Tests for _result_matches()."""

    def test_all_always_matches(self) -> None:
        assert _result_matches("SUCCESS", "All") is True
        assert _result_matches("FAIL", "All") is True
        assert _result_matches("SKIPPED (Short duration (<3 min))", "All") is True

    def test_success_exact_match(self) -> None:
        assert _result_matches("SUCCESS", "SUCCESS") is True

    def test_success_no_match(self) -> None:
        assert _result_matches("FAIL", "SUCCESS") is False
        assert _result_matches("SKIPPED (reason)", "SUCCESS") is False

    def test_fail_exact_match(self) -> None:
        assert _result_matches("FAIL", "FAIL") is True

    def test_fail_no_match(self) -> None:
        assert _result_matches("SUCCESS", "FAIL") is False

    def test_skipped_prefix_matches_any_reason(self) -> None:
        assert _result_matches("SKIPPED (Short duration (<3 min))", "SKIPPED") is True
        assert _result_matches("SKIPPED (Already downloaded)", "SKIPPED") is True
        assert _result_matches("SKIPPED", "SKIPPED") is True

    def test_skipped_does_not_match_success_or_fail(self) -> None:
        assert _result_matches("SUCCESS", "SKIPPED") is False
        assert _result_matches("FAIL", "SKIPPED") is False

    def test_skipped_prefix_only_not_substring(self) -> None:
        # A result that contains "SKIPPED" mid-string should NOT match
        assert _result_matches("NOT SKIPPED", "SKIPPED") is False
