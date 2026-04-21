"""Logging utilities for exception handling and diagnostics."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_local_timestamp() -> str:
    """Return current local timestamp as formatted string 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def log_exception(exc: Exception, context: str | None = None) -> None:
    """
    Log an exception to the global logger configured to write to error_log.txt.

    This helper is used by the app to ensure all swallowed exceptions are
    recorded with a full traceback.

    If logging has not yet been configured elsewhere, configure a basic
    handler so that errors are still written to the expected file.

    Args:
        exc: The exception to log.
        context: Optional context string to prepend to the exception message.
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            filename="error_log.txt",
            level=logging.ERROR,
            format="%(asctime)s %(message)s",
        )
    msg = f"{context}: {exc}" if context else str(exc)
    logger.exception(msg)
