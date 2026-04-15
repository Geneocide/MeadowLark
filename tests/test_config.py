"""Tests for the config module covering path resolution and environment overrides."""

import os
from pathlib import Path
from unittest import mock

from src import config


class TestPathResolution:
    """Tests for path resolution with environment variable fallbacks."""

    def test_error_log_path_default(self) -> None:
        """Test error log path uses default when env var not set."""
        with mock.patch.dict(os.environ, {}, clear=False):
            # Clear the env var if it exists
            os.environ.pop("VID_DL_ERROR_LOG", None)
            # Re-import to get fresh defaults
            import importlib

            importlib.reload(config)
            assert Path("error_log.txt") == config.ERROR_LOG_PATH

    def test_error_log_path_from_env(self) -> None:
        """Test error log path can be overridden via environment variable."""
        custom_path = "/custom/error.log"
        with mock.patch.dict(os.environ, {"VID_DL_ERROR_LOG": custom_path}):
            import importlib

            importlib.reload(config)
            assert Path(custom_path) == config.ERROR_LOG_PATH

    def test_history_log_path_default(self) -> None:
        """Test history log path uses default when env var not set."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_HISTORY_LOG", None)
            import importlib

            importlib.reload(config)
            assert Path("history_log.txt") == config.HISTORY_LOG_PATH

    def test_cookies_file_path(self) -> None:
        """Test cookies file path is under resources directory."""
        with mock.patch.dict(os.environ, {}, clear=False):
            import importlib

            importlib.reload(config)
            assert "cookies.txt" in str(config.COOKIES_FILE)
            assert config.COOKIES_FILE.name == "cookies.txt"

    def test_live_queue_file_path(self) -> None:
        """Test live queue file path is under resources directory."""
        with mock.patch.dict(os.environ, {}, clear=False):
            import importlib

            importlib.reload(config)
            assert "live_queue.txt" in str(config.LIVE_QUEUE_FILE)

    def test_playlist_files_paths(self) -> None:
        """Test all playlist file paths are configured."""
        with mock.patch.dict(os.environ, {}, clear=False):
            import importlib

            importlib.reload(config)
            assert config.PLAYLISTS_FILE.name == "playlists.txt"
            assert config.PLAYLISTS_720_FILE.name == "720playlists.txt"
            assert config.PLAYLISTS_AUDIO_FILE.name == "audio playlists.txt"

    def test_resources_dir_can_override(self) -> None:
        """Test resources directory can be overridden via environment."""
        custom_resources = "/custom/resources"
        with mock.patch.dict(os.environ, {"VID_DL_RESOURCES_DIR": custom_resources}):
            import importlib

            importlib.reload(config)
            assert Path(custom_resources) == config.RESOURCES_DIR

    def test_venv_scripts_dir_default(self) -> None:
        """Test venv scripts directory uses default path."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_VENV_SCRIPTS", None)
            import importlib

            importlib.reload(config)
            assert ".venv" in str(config.VENV_SCRIPTS_DIR)


class TestTimeoutConfiguration:
    """Tests for timeout configuration constants."""

    def test_http_timeout_default(self) -> None:
        """Test HTTP timeout uses default value."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_HTTP_TIMEOUT", None)
            import importlib

            importlib.reload(config)
            assert config.HTTP_TIMEOUT_SECONDS == 120

    def test_http_timeout_from_env(self) -> None:
        """Test HTTP timeout can be overridden via environment."""
        with mock.patch.dict(os.environ, {"VID_DL_HTTP_TIMEOUT": "300"}):
            import importlib

            importlib.reload(config)
            assert config.HTTP_TIMEOUT_SECONDS == 300

    def test_socket_timeout_default(self) -> None:
        """Test socket timeout uses default value."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_SOCKET_TIMEOUT", None)
            import importlib

            importlib.reload(config)
            assert config.SOCKET_TIMEOUT_SECONDS == 120

    def test_http_request_timeout_default(self) -> None:
        """Test HTTP request timeout uses default value."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_HTTP_REQUEST_TIMEOUT", None)
            import importlib

            importlib.reload(config)
            assert config.HTTP_REQUEST_TIMEOUT_SECONDS == 5

    def test_http_request_timeout_from_env(self) -> None:
        """Test HTTP request timeout can be overridden."""
        with mock.patch.dict(os.environ, {"VID_DL_HTTP_REQUEST_TIMEOUT": "10"}):
            import importlib

            importlib.reload(config)
            assert config.HTTP_REQUEST_TIMEOUT_SECONDS == 10


class TestDownloadConfiguration:
    """Tests for download configuration."""

    def test_max_fragment_retries_default(self) -> None:
        """Test max fragment retries uses default value."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_MAX_FRAGMENT_RETRIES", None)
            import importlib

            importlib.reload(config)
            assert config.MAX_FRAGMENT_RETRIES == 10

    def test_max_fragment_retries_from_env(self) -> None:
        """Test max fragment retries can be overridden."""
        with mock.patch.dict(os.environ, {"VID_DL_MAX_FRAGMENT_RETRIES": "20"}):
            import importlib

            importlib.reload(config)
            assert config.MAX_FRAGMENT_RETRIES == 20

    def test_http_ok_status_code(self) -> None:
        """Test HTTP OK status code constant."""
        assert config.HTTP_OK == 200


class TestPodcastConfiguration:
    """Tests for podcast-related configuration."""

    def test_podcast_min_duration_default(self) -> None:
        """Test minimum podcast duration uses default (3 minutes = 180 seconds)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_PODCAST_MIN_DURATION_SECONDS", None)
            import importlib

            importlib.reload(config)
            assert config.PODCAST_MIN_DURATION_SECONDS == 180

    def test_podcast_min_duration_from_env(self) -> None:
        """Test minimum podcast duration can be overridden."""
        with mock.patch.dict(
            os.environ,
            {"VID_DL_PODCAST_MIN_DURATION_SECONDS": "300"},
        ):
            import importlib

            importlib.reload(config)
            assert config.PODCAST_MIN_DURATION_SECONDS == 300

    def test_sponsorblock_cache_ttl_default(self) -> None:
        """Test SponsorBlock cache TTL uses default (6 hours)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_SPONSORBLOCK_CACHE_TTL_HOURS", None)
            import importlib

            importlib.reload(config)
            assert config.SPONSORBLOCK_CACHE_TTL_HOURS == 6

    def test_sponsorblock_cache_ttl_from_env(self) -> None:
        """Test SponsorBlock cache TTL can be overridden."""
        with mock.patch.dict(os.environ, {"VID_DL_SPONSORBLOCK_CACHE_TTL_HOURS": "12"}):
            import importlib

            importlib.reload(config)
            assert config.SPONSORBLOCK_CACHE_TTL_HOURS == 12

    def test_live_queue_check_interval_default(self) -> None:
        """Test live queue check interval uses default (30 minutes)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_LIVE_QUEUE_CHECK_INTERVAL_MINUTES", None)
            import importlib

            importlib.reload(config)
            assert config.LIVE_QUEUE_CHECK_INTERVAL_MINUTES == 30

    def test_live_queue_check_interval_from_env(self) -> None:
        """Test live queue check interval can be overridden."""
        with mock.patch.dict(
            os.environ,
            {"VID_DL_LIVE_QUEUE_CHECK_INTERVAL_MINUTES": "60"},
        ):
            import importlib

            importlib.reload(config)
            assert config.LIVE_QUEUE_CHECK_INTERVAL_MINUTES == 60

    def test_podcast_lookahead_max_attempts_default(self) -> None:
        """Test podcast lookahead max attempts uses default (5)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_PODCAST_LOOKAHEAD_MAX_ATTEMPTS", None)
            import importlib

            importlib.reload(config)
            assert config.PODCAST_LOOKAHEAD_MAX_ATTEMPTS == 5


class TestDisplayConfiguration:
    """Tests for display configuration."""

    def test_label_output_font_default(self) -> None:
        """Test label output font uses default (Arial)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_LABEL_OUTPUT_FONT", None)
            import importlib

            importlib.reload(config)
            assert config.LABEL_OUTPUT_FONT_NAME == "Arial"

    def test_label_output_font_from_env(self) -> None:
        """Test label output font can be overridden."""
        with mock.patch.dict(os.environ, {"VID_DL_LABEL_OUTPUT_FONT": "Courier"}):
            import importlib

            importlib.reload(config)
            assert config.LABEL_OUTPUT_FONT_NAME == "Courier"

    def test_label_output_font_size_default(self) -> None:
        """Test label output font size uses default (16)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_LABEL_OUTPUT_FONT_SIZE", None)
            import importlib

            importlib.reload(config)
            assert config.LABEL_OUTPUT_FONT_SIZE == 16

    def test_label_ready_text_default(self) -> None:
        """Test label ready text uses default."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_LABEL_READY_TEXT", None)
            import importlib

            importlib.reload(config)
            assert config.LABEL_READY_TEXT == "[ Ready ]"


class TestPostProcessingConfiguration:
    """Tests for post-processing configuration."""

    def test_merge_output_format_default(self) -> None:
        """Test merge output format uses default (mp4)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_MERGE_OUTPUT_FORMAT", None)
            import importlib

            importlib.reload(config)
            assert config.DEFAULT_MERGE_OUTPUT_FORMAT == "mp4"


class TestDebugConfiguration:
    """Tests for debug configuration."""

    def test_logfile_migration_enabled_default(self) -> None:
        """Test logfile migration is enabled by default."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VID_DL_LOGFILE_MIGRATION", None)
            import importlib

            importlib.reload(config)
            assert config.LOGFILE_MIGRATION_ENABLED is True

    def test_logfile_migration_disabled_via_env(self) -> None:
        """Test logfile migration can be disabled via environment."""
        with mock.patch.dict(os.environ, {"VID_DL_LOGFILE_MIGRATION": "false"}):
            import importlib

            importlib.reload(config)
            assert config.LOGFILE_MIGRATION_ENABLED is False


class TestConfigConstants:
    """Integration tests for config constant accessibility."""

    def test_all_constants_accessible(self) -> None:
        """Test that all configurations are accessible as module attributes."""
        # Verify all major groups are accessible
        assert hasattr(config, "ERROR_LOG_PATH")
        assert hasattr(config, "HISTORY_LOG_PATH")
        assert hasattr(config, "HTTP_TIMEOUT_SECONDS")
        assert hasattr(config, "PODCAST_MIN_DURATION_SECONDS")
        assert hasattr(config, "SPONSORBLOCK_CACHE_TTL_HOURS")
        assert hasattr(config, "LABEL_OUTPUT_FONT_NAME")

    def test_paths_are_path_objects(self) -> None:
        """Test that all paths are Path objects."""
        assert isinstance(config.ERROR_LOG_PATH, Path)
        assert isinstance(config.HISTORY_LOG_PATH, Path)
        assert isinstance(config.COOKIES_FILE, Path)
        assert isinstance(config.LIVE_QUEUE_FILE, Path)
        assert isinstance(config.PLAYLISTS_FILE, Path)
        assert isinstance(config.VENV_SCRIPTS_DIR, Path)

    def test_numeric_constants_are_integers(self) -> None:
        """Test that numeric constants are integers."""
        assert isinstance(config.HTTP_TIMEOUT_SECONDS, int)
        assert isinstance(config.SOCKET_TIMEOUT_SECONDS, int)
        assert isinstance(config.MAX_FRAGMENT_RETRIES, int)
        assert isinstance(config.PODCAST_MIN_DURATION_SECONDS, int)
        assert isinstance(config.HTTP_OK, int)
