from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class UsageWindow:
    label: str
    used_percent: float
    reset_at: datetime | None
    used: float | None = None
    limit: float | None = None


def parse_timestamp(value: str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1_000_000_000_000:
            seconds = seconds / 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    normalized = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)
