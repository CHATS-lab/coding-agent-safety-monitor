"""Hook logger setup and session log directory management."""

import logging
from pathlib import Path

SEPARATOR_WIDTH = 70
SEPARATOR = "=" * SEPARATOR_WIDTH
SEPARATOR_THIN = "-" * SEPARATOR_WIDTH


def get_session_log_dir(conversation_id: str) -> Path:
    """Return <cwd>/logs/safety_monitor/, creating it on first call.

    Also writes a `.gitignore` containing `*` so audit output is never
    committed by accident. The `conversation_id` argument is accepted for
    API compatibility but does not affect the directory itself — per-session
    filenames are handled by `setup_hook_logger` and `append_usage_record`.
    """
    log_dir = Path.cwd() / "logs" / "safety_monitor"
    log_dir.mkdir(parents=True, exist_ok=True)
    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    return log_dir


def setup_hook_logger(
    log_name: str, conversation_id: str, level: int = logging.INFO
) -> logging.Logger:
    """Set up a per-session file logger.

    The log file is named `monitor_<session8>.log` where `<session8>` is the
    first 8 characters of the session id, so multiple sessions in the same
    cwd remain distinguishable without nesting subdirectories.
    """
    log_dir = get_session_log_dir(conversation_id=conversation_id)
    short_id = (conversation_id or "unknown")[:8]
    log_file = log_dir / f"monitor_{short_id}.log"

    logger_name = f"{log_name}_{short_id}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    logger.handlers.clear()
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def log_separator(
    logger: logging.Logger, char: str = "=", length: int = SEPARATOR_WIDTH
) -> None:
    """Log a separator line."""
    logger.info(char * length)
