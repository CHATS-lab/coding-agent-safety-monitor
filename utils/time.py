"""UTC time utilities."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def utc_now_compact() -> str:
    """Return the current UTC time as a compact string (YYYYMMDDHHMMSSffffff)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
