from datetime import datetime, timedelta, timezone

from opencode_limits.cache import (
    FORMAT_VERSION,
    STALE_FALLBACK_SECONDS,
    CacheRecord,
    CachedWindow,
    is_fresh,
    is_stale_allowed,
)


def test_cache_ttl_expiration() -> None:
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = _record(fetched_at=fetched_at)

    assert not is_fresh(
        record,
        ttl_seconds=60,
        auth_fingerprint="abc",
        now=fetched_at + timedelta(seconds=61),
    )


def test_cache_busts_on_reset_boundary() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = _record(fetched_at=now, reset_at=now - timedelta(seconds=1))

    assert not is_fresh(
        record,
        ttl_seconds=300,
        auth_fingerprint="abc",
        now=now,
    )


def test_cache_busts_on_fingerprint_mismatch() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = _record(fetched_at=now, fingerprint="abc")

    assert not is_fresh(
        record,
        ttl_seconds=300,
        auth_fingerprint="def",
        now=now,
    )


def test_stale_fallback_allowed_within_window() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = _record(fetched_at=now - timedelta(seconds=STALE_FALLBACK_SECONDS - 10))

    assert is_stale_allowed(
        record,
        max_age_seconds=STALE_FALLBACK_SECONDS,
        auth_fingerprint="abc",
        now=now,
    )


def _record(
    *,
    fetched_at: datetime,
    reset_at: datetime | None = None,
    fingerprint: str = "abc",
) -> CacheRecord:
    codex = {"5HR": CachedWindow(used_percent=12.0, reset_at=reset_at)}
    return CacheRecord(
        fetched_at=fetched_at,
        codex=codex,
        copilot=None,
        auth_fingerprint=fingerprint,
        format_version=FORMAT_VERSION,
    )
