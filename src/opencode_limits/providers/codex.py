from __future__ import annotations

from typing import Any, Iterable

import httpx

from opencode_limits.auth import AuthTokens
from opencode_limits.models import UsageWindow, parse_timestamp

CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def fetch_codex_usage(
    tokens: AuthTokens, client: httpx.Client | None = None
) -> list[UsageWindow]:
    headers = {
        "Authorization": f"Bearer {tokens.openai}",
        "chatgpt-account-id": tokens.chatgpt_account_id,
    }
    if client is None:
        with httpx.Client(headers=headers, timeout=10.0) as session:
            response = session.get(CODEX_USAGE_URL)
            response.raise_for_status()
            return parse_codex_usage(response.json())

    response = client.get(CODEX_USAGE_URL, headers=headers)
    response.raise_for_status()
    return parse_codex_usage(response.json())


def parse_codex_usage(payload: dict[str, Any]) -> list[UsageWindow]:
    return _parse_windows(payload.get("rate_limit", []), prefix="")


def _parse_windows(entries: Any, prefix: str) -> list[UsageWindow]:
    parsed: list[UsageWindow] = []
    for entry in _iter_entries(entries):
        label = _build_label(entry, prefix)
        used_percent = _coerce_used_percent(entry)
        parsed.append(
            UsageWindow(
                label=label,
                used_percent=used_percent,
                reset_at=parse_timestamp(entry.get("reset_at")),
                used=_coerce_number(entry.get("used")),
                limit=_coerce_number(entry.get("limit")),
            )
        )
    return parsed


def _iter_entries(entries: Any) -> Iterable[dict[str, Any]]:
    if isinstance(entries, dict):
        if _looks_like_entry(entries):
            yield entries
            return
        for key, value in entries.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("window", key)
                yield entry
        return
    for entry in entries:
        if isinstance(entry, dict):
            yield entry


def _looks_like_entry(entry: dict[str, Any]) -> bool:
    return any(key in entry for key in ("used_percent", "limit", "reset_at", "used"))


def _build_label(entry: dict[str, Any], prefix: str) -> str:
    window_name = entry.get("window") or entry.get("name") or "window"
    window_label = str(window_name).replace("_", " ")
    normalized = window_label.lower()
    compact = normalized.replace(" ", "").replace("-", "")
    label_map = {
        "primary window": "5HR",
        "secondary window": "Weekly",
    }
    if compact in {"5h", "5hr", "5hrs", "5hour", "5hours", "fivehour", "fivehours"}:
        window_label = "5HR"
    else:
        window_label = label_map.get(normalized, window_label)
    if "window" not in window_label.lower() and window_label.lower() not in {
        "weekly",
        "5hr",
    }:
        window_label = f"{window_label} window"
    if prefix:
        return f"{prefix} {window_label}"
    return str(window_label)


def _coerce_used_percent(entry: dict[str, Any]) -> float:
    used_percent = entry.get("used_percent")
    if used_percent is not None:
        return float(used_percent)
    used = _coerce_number(entry.get("used"))
    limit = _coerce_number(entry.get("limit"))
    if used is None or limit in (None, 0):
        return 0.0
    return float(used) / float(limit) * 100.0


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
