"""Simple debug logging for standalone sandbox."""

import logging
import os
from typing import Optional

_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Get or create the debug logger."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("sandbox_runtime.debug")
        _logger.setLevel(logging.DEBUG)
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("[SandboxDebug] %(message)s")
            )
            _logger.addHandler(handler)
    return _logger


def log_for_debugging(
    message: str,
    options: Optional[dict[str, str]] = None,
) -> None:
    """Log a debug message if DEBUG environment variable is set."""
    # Only log if DEBUG environment variable is set
    if not os.environ.get("DEBUG"):
        return

    level = (options or {}).get("level", "info")
    logger = _get_logger()

    if level == "error":
        logger.error(message)
    elif level == "warn":
        logger.warning(message)
    else:
        logger.info(message)

