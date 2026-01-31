from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from opencode_limits.auth import AuthTokens
from opencode_limits.models import UsageWindow, parse_timestamp

DEFAULT_CACHE_TTL_SECONDS = 180
STALE_FALLBACK_SECONDS = 24 * 60 * 60
FORMAT_VERSION = 1


@dataclass(frozen=True)
class CachedWindow:
    used_percent: float
    reset_at: datetime | None


@dataclass(frozen=True)
class CacheRecord:
    fetched_at: datetime
    codex: dict[str, CachedWindow]
    copilot: CachedWindow | None
    auth_fingerprint: str
    format_version: int = FORMAT_VERSION


def cache_path(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path("~/.cache").expanduser()
    return base / "opencode-limits" / "tmux.json"


def build_auth_fingerprint(tokens: AuthTokens) -> str:
    digest = hashlib.sha256()
    digest.update(tokens.openai.encode("utf-8"))
    digest.update(b":")
    digest.update(tokens.github_copilot.encode("utf-8"))
    digest.update(b":")
    digest.update(tokens.chatgpt_account_id.encode("utf-8"))
    return digest.hexdigest()


def build_cache_record(
    codex_windows: Iterable[UsageWindow] | None,
    copilot_window: UsageWindow | None,
    tokens: AuthTokens,
    fetched_at: datetime | None = None,
) -> CacheRecord:
    codex: dict[str, CachedWindow] = {}
    for window in codex_windows or []:
        label = _normalize_codex_label(window.label)
        if not label:
            continue
        codex[label] = _to_cached_window(window)

    copilot = _to_cached_window(copilot_window) if copilot_window else None
    return CacheRecord(
        fetched_at=fetched_at or datetime.now(timezone.utc),
        codex=codex,
        copilot=copilot,
        auth_fingerprint=build_auth_fingerprint(tokens),
        format_version=FORMAT_VERSION,
    )


def load_cache(path: Path) -> CacheRecord | None:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    fetched_at = parse_timestamp(payload.get("fetched_at"))
    auth_fingerprint = payload.get("auth_fingerprint")
    format_version = payload.get("format_version")
    if fetched_at is None or not auth_fingerprint or format_version is None:
        return None

    try:
        format_version_int = int(format_version)
    except (TypeError, ValueError):
        return None

    codex_payload = payload.get("codex")
    codex: dict[str, CachedWindow] = {}
    if isinstance(codex_payload, dict):
        for label, entry in codex_payload.items():
            window = _parse_cached_window(entry)
            if window is not None:
                codex[str(label)] = window

    copilot = _parse_cached_window(payload.get("copilot"))

    return CacheRecord(
        fetched_at=fetched_at,
        codex=codex,
        copilot=copilot,
        auth_fingerprint=str(auth_fingerprint),
        format_version=format_version_int,
    )


def save_cache(path: Path, record: CacheRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": record.fetched_at.astimezone(timezone.utc).isoformat(),
        "codex": {
            label: _serialize_cached_window(window)
            for label, window in record.codex.items()
        },
        "copilot": _serialize_cached_window(record.copilot),
        "auth_fingerprint": record.auth_fingerprint,
        "format_version": record.format_version,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def is_fresh(
    record: CacheRecord,
    ttl_seconds: int,
    auth_fingerprint: str,
    format_version: int = FORMAT_VERSION,
    now: datetime | None = None,
) -> bool:
    if record.format_version != format_version:
        return False
    if record.auth_fingerprint != auth_fingerprint:
        return False
    current = now or datetime.now(timezone.utc)
    age_seconds = (current - record.fetched_at).total_seconds()
    if age_seconds > ttl_seconds:
        return False
    if _has_reset_passed(record, current):
        return False
    return True


def is_stale_allowed(
    record: CacheRecord,
    max_age_seconds: int,
    auth_fingerprint: str,
    format_version: int = FORMAT_VERSION,
    now: datetime | None = None,
) -> bool:
    if record.format_version != format_version:
        return False
    if record.auth_fingerprint != auth_fingerprint:
        return False
    current = now or datetime.now(timezone.utc)
    age_seconds = (current - record.fetched_at).total_seconds()
    if age_seconds > max_age_seconds:
        return False
    if _has_reset_passed(record, current):
        return False
    return True


def _parse_cached_window(payload: Any) -> CachedWindow | None:
    if not isinstance(payload, dict):
        return None
    used_percent = payload.get("used_percent")
    if used_percent is None:
        return None
    try:
        percent = float(used_percent)
    except (TypeError, ValueError):
        return None
    reset_at = parse_timestamp(payload.get("reset_at"))
    return CachedWindow(used_percent=percent, reset_at=reset_at)


def _serialize_cached_window(window: CachedWindow | None) -> dict[str, Any] | None:
    if window is None:
        return None
    reset_at = (
        window.reset_at.astimezone(timezone.utc).isoformat()
        if window.reset_at
        else None
    )
    return {"used_percent": window.used_percent, "reset_at": reset_at}


def _to_cached_window(window: UsageWindow) -> CachedWindow:
    return CachedWindow(used_percent=window.used_percent, reset_at=window.reset_at)


def _normalize_codex_label(label: str) -> str | None:
    normalized = label.strip().lower()
    if normalized == "5hr":
        return "5HR"
    if normalized == "weekly":
        return "Weekly"
    return None


def _has_reset_passed(record: CacheRecord, now: datetime) -> bool:
    for window in record.codex.values():
        if window.reset_at and window.reset_at <= now:
            return True
    if record.copilot and record.copilot.reset_at and record.copilot.reset_at <= now:
        return True
    return False
