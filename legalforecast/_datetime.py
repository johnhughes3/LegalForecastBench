"""Internal datetime formatting helpers."""

from datetime import UTC, datetime


def format_utc_iso_z(value: datetime) -> str:
    """Format a datetime as UTC ISO-8601 with a trailing ``Z``."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
