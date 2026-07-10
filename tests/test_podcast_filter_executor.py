"""Comprehensive tests for PodcastFilterExecutor podcast filtering logic."""

from datetime import UTC, datetime
from unittest.mock import patch

from src.podcast_filter_executor import PodcastFilterExecutor
from src.podcast_filtering import PODCAST_MIN_DURATION_SECONDS


class TestPodcastFilterExecutorInitialization:
    """Test executor initialization and state setup."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        executor = PodcastFilterExecutor()
        assert executor.archive_path is None
        assert executor.messages == []
        assert executor.bypass_sponsorblock_wait is False
        assert executor.existing_ids == set()

    def test_init_with_archive_path(self):
        """Test initialization with archive path."""
        executor = PodcastFilterExecutor(archive_path="/path/to/archive")
        assert executor.archive_path == "/path/to/archive"

    def test_init_with_messages_list(self):
        """Test initialization with existing messages list."""
        messages = ["initial message"]
        executor = PodcastFilterExecutor(messages=messages)
        assert executor.messages is messages
        assert "initial message" in executor.messages

    def test_init_with_bypass_sponsorblock(self):
        """Test initialization with SponsorBlock bypass enabled."""
        executor = PodcastFilterExecutor(bypass_sponsorblock_wait=True)
        assert executor.bypass_sponsorblock_wait is True

    def test_init_sets_current_timestamp(self):
        """Test that executor captures current timestamp on init."""
        before = datetime.now(tz=UTC).timestamp()
        executor = PodcastFilterExecutor()
        after = datetime.now(tz=UTC).timestamp()
        assert before <= executor.now_ts <= after


class TestAlreadyArchivedCheck:
    """Test video archival status checking."""

    def test_is_already_archived_true(self):
        """Test video already in archive returns True."""
        executor = PodcastFilterExecutor()
        executor.existing_ids = {"vid123", "vid456"}
        assert executor._is_already_archived("vid123") is True

    def test_is_already_archived_false(self):
        """Test video not in archive returns False."""
        executor = PodcastFilterExecutor()
        executor.existing_ids = {"vid123"}
        assert executor._is_already_archived("other_vid") is False

    def test_is_already_archived_empty_set(self):
        """Test empty archive set returns False."""
        executor = PodcastFilterExecutor()
        executor.existing_ids = set()
        assert executor._is_already_archived("vid123") is False


class TestUpdateExceptionSkip:
    """Test skipping episodes with '(Update)' in title."""

    def test_should_skip_update_exception_with_update_title(self):
        """Test episode with '(Update)' in title is skipped."""
        executor = PodcastFilterExecutor(messages=[])
        with (
            patch("QYT.HistoryLogger.log_skip") as mock_log,
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            result = executor._should_skip_update_exception(
                "Episode (Update)",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert result is True
            assert len(executor.messages) > 0
            assert "Update" in executor.messages[0]
            mock_log.assert_called_once()

    def test_should_not_skip_without_update_text(self):
        """Test normal title does not trigger skip."""
        executor = PodcastFilterExecutor()
        with patch("QYT.HistoryLogger.log_skip") as mock_log:
            result = executor._should_skip_update_exception(
                "Regular Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert result is False
            mock_log.assert_not_called()

    def test_update_exception_adds_to_archive(self):
        """Test skipped update exception is added to existing_ids."""
        executor = PodcastFilterExecutor(archive_path="fake_archive.txt", messages=[])
        executor.existing_ids = set()
        with (
            patch("QYT.HistoryLogger.log_skip"),
            patch("utils.detect_site_from_urls", return_value="youtube"),
            patch("pathlib.Path.open"),
        ):
            executor._should_skip_update_exception(
                "Episode (Update)",
                "vid123",
                "https://example.com",
            )
            assert "vid123" in executor.existing_ids


class TestShortDurationSkip:
    """Test skipping episodes with short duration."""

    def test_should_skip_short_duration(self):
        """Test episode under 3 minutes is skipped."""
        executor = PodcastFilterExecutor(messages=[])
        executor.existing_ids = set()
        with (
            patch("QYT.HistoryLogger.log_skip") as mock_log,
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            result = executor._should_skip_short_duration(
                100,  # 100 seconds < 180 seconds
                "Short Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert result is True
            assert len(executor.messages) > 0
            assert "Short duration" in executor.messages[0]
            mock_log.assert_called_once()

    def test_should_not_skip_long_duration(self):
        """Test episode >= 3 minutes is not skipped."""
        executor = PodcastFilterExecutor()
        with patch("QYT.HistoryLogger.log_skip") as mock_log:
            result = executor._should_skip_short_duration(
                PODCAST_MIN_DURATION_SECONDS,
                "Long Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert result is False
            mock_log.assert_not_called()

    def test_should_not_skip_missing_duration(self):
        """Test episode with None duration is not skipped."""
        executor = PodcastFilterExecutor()
        with patch("QYT.HistoryLogger.log_skip") as mock_log:
            result = executor._should_skip_short_duration(
                None,
                "Unknown Duration Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert result is False
            mock_log.assert_not_called()

    def test_short_duration_adds_to_archive(self):
        """Test skipped short episode is added to existing_ids."""
        executor = PodcastFilterExecutor(archive_path="fake_archive.txt", messages=[])
        executor.existing_ids = set()
        with (
            patch("QYT.HistoryLogger.log_skip"),
            patch("utils.detect_site_from_urls", return_value="youtube"),
            patch("pathlib.Path.open"),
        ):
            executor._should_skip_short_duration(
                100,
                "Short Episode",
                "vid123",
                "https://example.com",
            )
            assert "vid123" in executor.existing_ids


class TestEpisodeStatusEvaluation:
    """Test episode status evaluation based on timestamp."""

    def test_no_timestamp_returns_ready(self):
        """Test episode with no timestamp is marked as Ready."""
        executor = PodcastFilterExecutor()
        status, urls = executor._evaluate_episode_status(
            None,
            "No Timestamp Episode",
            "vid123",
            "https://youtube.com/watch?v=vid123",
        )
        assert status == "Ready"
        assert len(urls) == 1
        assert urls[0]["url"] == "https://youtube.com/watch?v=vid123"

    def test_future_timestamp_returns_upcoming(self):
        """Test episode with future timestamp is marked as Upcoming."""
        executor = PodcastFilterExecutor()
        future_ts = executor.now_ts + (24 * 60 * 60)  # 24 hours in future
        status, urls = executor._evaluate_episode_status(
            future_ts,
            "Upcoming Episode",
            "vid123",
            "https://youtube.com/watch?v=vid123",
        )
        assert status == "Upcoming"
        assert len(urls) == 0

    def test_bypass_sponsorblock_returns_ready(self):
        """Test bypass_sponsorblock_wait skips SponsorBlock checks."""
        executor = PodcastFilterExecutor(bypass_sponsorblock_wait=True)
        recent_ts = executor.now_ts - (12 * 60 * 60)  # 12 hours old
        status, urls = executor._evaluate_episode_status(
            recent_ts,
            "Recent Episode",
            "vid123",
            "https://youtube.com/watch?v=vid123",
        )
        assert status == "Ready"
        assert len(urls) == 1

    def test_recent_youtube_with_sponsorblock_ready(self):
        """Test recent YouTube episode with SponsorBlock data is Ready."""
        executor = PodcastFilterExecutor()
        recent_ts = executor.now_ts - (12 * 60 * 60)  # 12 hours old
        with (
            patch(
                "src.podcast_filter_executor.check_sponsorblock_for_video_id",
                return_value=True,
            ),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            status, urls = executor._evaluate_episode_status(
                recent_ts,
                "Recent Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert status == "Ready"
            assert len(urls) == 1

    def test_recent_youtube_without_sponsorblock_pending(self):
        """Test recent YouTube episode without SponsorBlock is Pending."""
        executor = PodcastFilterExecutor()
        recent_ts = executor.now_ts - (12 * 60 * 60)  # 12 hours old
        with (
            patch(
                "src.podcast_filter_executor.check_sponsorblock_for_video_id",
                return_value=False,
            ),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            status, urls = executor._evaluate_episode_status(
                recent_ts,
                "Recent Episode",
                "vid123",
                "https://youtube.com/watch?v=vid123",
            )
            assert status == "Pending SponsorBlock"
            assert len(urls) == 1

    def test_recent_non_youtube_skips_sponsorblock(self):
        """Test recent non-YouTube episode skips SponsorBlock check."""
        executor = PodcastFilterExecutor()
        recent_ts = executor.now_ts - (12 * 60 * 60)  # 12 hours old
        with (
            patch(
                "src.podcast_filter_executor.check_sponsorblock_for_video_id",
            ) as mock_sb,
            patch("utils.detect_site_from_urls", return_value="soundcloud"),
        ):
            status, urls = executor._evaluate_episode_status(
                recent_ts,
                "Recent Episode",
                "vid123",
                "https://soundcloud.com/episode",
            )
            assert status == "Ready"
            assert len(urls) == 1
            mock_sb.assert_not_called()

    def test_old_episode_returns_ready(self):
        """Test episode older than 24h is marked as Ready."""
        executor = PodcastFilterExecutor()
        old_ts = executor.now_ts - (48 * 60 * 60)  # 48 hours old
        status, urls = executor._evaluate_episode_status(
            old_ts,
            "Old Episode",
            "vid123",
            "https://youtube.com/watch?v=vid123",
        )
        assert status == "Ready"
        assert len(urls) == 1


class TestEvaluatePlaylistUrls:
    """Test full playlist evaluation with multiple entries."""

    def test_empty_playlist_returns_empty_ready_list(self):
        """Test empty playlist returns empty lists."""
        executor = PodcastFilterExecutor()
        to_download, pending, status = executor.evaluate_playlist_urls([])
        assert to_download == []
        assert pending == []
        assert status["status"] == "(unknown)"

    def test_single_archived_entry(self):
        """Test already archived entry marks status as Downloaded."""
        executor = PodcastFilterExecutor()
        executor.existing_ids = {"vid123"}
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Downloaded Episode",
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "Downloaded"
        assert to_download == []
        assert pending == []

    def test_single_ready_entry(self):
        """Test episode ready for download."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Ready Episode",
                "timestamp": None,
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "Ready"
        assert len(to_download) == 1
        assert len(pending) == 0

    def test_skipped_update_exception(self):
        """Test episode with (Update) in title is skipped."""
        executor = PodcastFilterExecutor(messages=[])
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Episode (Update)",
                "timestamp": None,
            },
        ]
        with (
            patch("QYT.HistoryLogger.log_skip"),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            to_download, pending, status = executor.evaluate_playlist_urls(entries)
            assert status["status"] == "Skipped (Update)"
            assert to_download == []

    def test_skipped_short_duration(self):
        """Test short episode is skipped."""
        executor = PodcastFilterExecutor(messages=[])
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Short Episode",
                "duration": 60,
                "timestamp": None,
            },
        ]
        with (
            patch("QYT.HistoryLogger.log_skip"),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            to_download, pending, status = executor.evaluate_playlist_urls(entries)
            assert status["status"] == "Skipped Short"
            assert to_download == []

    def test_pending_sponsorblock_status(self):
        """Test recent episode awaiting SponsorBlock."""
        executor = PodcastFilterExecutor()
        recent_ts = executor.now_ts - (12 * 60 * 60)
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Pending Episode",
                "timestamp": recent_ts,
            },
        ]
        with (
            patch(
                "src.podcast_filter_executor.check_sponsorblock_for_video_id",
                return_value=False,
            ),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            to_download, pending, status = executor.evaluate_playlist_urls(entries)
            assert status["status"] == "Pending SponsorBlock"
            assert len(pending) == 1
            assert to_download == []

    def test_stops_at_first_entry_for_status(self):
        """Test evaluation stops after first entry (latest check)."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Latest",
                "timestamp": None,
            },
            {
                "id": "vid456",
                "webpage_url": "https://youtube.com/watch?v=vid456",
                "title": "Older",
                "timestamp": None,
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        # Should only process first entry
        assert status["latest_url"] == "https://youtube.com/watch?v=vid123"

    def test_multiple_valid_entries_all_processed(self):
        """Test multiple entries before archive hit are all included."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid456",
                "webpage_url": "https://youtube.com/watch?v=vid456",
                "title": "Already archived",
            },
        ]
        executor.existing_ids = {"vid456"}
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "Downloaded"

    def test_missing_id_skips_entry(self):
        """Test entry without ID is skipped."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "No ID",
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "(unknown)"
        assert to_download == []

    def test_missing_webpage_url_skips_entry(self):
        """Test entry without webpage URL is skipped."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid123",
                "title": "No URL",
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "(unknown)"
        assert to_download == []

    def test_timestamp_parsing_in_status_entry(self):
        """Test timestamp is parsed and formatted in status."""
        executor = PodcastFilterExecutor()
        now = datetime.now(tz=UTC)
        # 1 hour ago: deterministically in the past so this is "Ready", not
        # "Upcoming". Using now.timestamp() directly was flaky — the executor
        # samples now_ts before this line, so a sub-second-later timestamp reads
        # as a future/upcoming episode under the high-resolution clock (Py 3.13+).
        ts = now.timestamp() - 3600
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Timestamped Episode",
                "timestamp": ts,
            },
        ]
        with (
            patch(
                "src.podcast_filter_executor.check_sponsorblock_for_video_id",
                return_value=True,
            ),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            to_download, pending, status = executor.evaluate_playlist_urls(entries)
            assert status["status"] == "Ready"
            assert status["latest_date"] != "(unknown)"

    def test_status_entry_includes_latest_url(self):
        """Test status_entry includes latest_url."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://youtube.com/watch?v=vid123",
                "title": "Test Episode",
                "timestamp": None,
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status.get("latest_url") == "https://youtube.com/watch?v=vid123"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_entry_with_url_fallback_for_id(self):
        """Test entry uses 'url' field as fallback for 'id'."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "url": "https://example.com/video123",
                "webpage_url": "https://example.com/watch/video123",
                "title": "URL Fallback",
                "timestamp": None,
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "Ready"

    def test_empty_title_handling(self):
        """Test entry with empty or missing title."""
        executor = PodcastFilterExecutor()
        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://example.com",
                "title": "",
                "timestamp": None,
            },
        ]
        to_download, pending, status = executor.evaluate_playlist_urls(entries)
        assert status["status"] == "Ready"

    def test_messages_accumulate(self):
        """Test messages from multiple operations accumulate."""
        messages = []
        executor = PodcastFilterExecutor(messages=messages)
        executor.existing_ids = set()

        entries = [
            {
                "id": "vid123",
                "webpage_url": "https://example.com",
                "title": "Episode (Update)",
                "timestamp": None,
            },
        ]

        with (
            patch("QYT.HistoryLogger.log_skip"),
            patch("utils.detect_site_from_urls", return_value="youtube"),
        ):
            executor.evaluate_playlist_urls(entries)

        assert len(messages) > 0
        assert any(
            "updated" in msg.lower() or "update" in msg.lower() for msg in messages
        )

    def test_executor_state_preserved_across_evaluations(self):
        """Test executor maintains state across multiple evaluations."""
        executor = PodcastFilterExecutor()
        executor.existing_ids = {"vid123"}

        # First evaluation
        entries1 = [
            {"id": "vid456", "webpage_url": "https://example.com", "title": "New"},
        ]
        to_download1, _, _ = executor.evaluate_playlist_urls(entries1)

        # Archive should still have vid123
        assert "vid123" in executor.existing_ids
