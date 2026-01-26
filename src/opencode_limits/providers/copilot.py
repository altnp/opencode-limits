from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx

from opencode_limits.auth import AuthTokens
from opencode_limits.models import UsageWindow, parse_timestamp

COPILOT_PRO_MONTHLY_LIMIT = 300
GITHUB_API_URL = "https://api.github.com"


def fetch_copilot_usage(
    tokens: AuthTokens, client: httpx.Client | None = None
) -> UsageWindow:
    headers = {
        "Authorization": f"Bearer {tokens.github_copilot}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "opencode-limits",
    }
    if client is None:
        with httpx.Client(headers=headers, timeout=10.0) as session:
            return _fetch_with_session(session)

    return _fetch_with_session(client, headers=headers)


def _fetch_with_session(
    session: httpx.Client, headers: dict[str, str] | None = None
) -> UsageWindow:
    billing_window = _fetch_billing_usage(session, headers=headers)
    if billing_window is not None:
        return billing_window
    return _fetch_internal_usage(session, headers=headers)


def _fetch_billing_usage(
    session: httpx.Client, headers: dict[str, str] | None = None
) -> UsageWindow | None:
    user_response = session.get(f"{GITHUB_API_URL}/user", headers=headers)
    user_response.raise_for_status()
    login = user_response.json().get("login")
    if not login:
        raise RuntimeError("GitHub response missing login")

    today = date.today()
    usage_response = session.get(
        f"{GITHUB_API_URL}/users/{login}/settings/billing/premium_request/usage",
        params={"year": today.year, "month": today.month},
        headers=headers,
    )
    if usage_response.status_code == 404:
        return None
    usage_response.raise_for_status()
    used = parse_copilot_usage(usage_response.json())
    return build_copilot_window(used, today=today)


def _fetch_internal_usage(
    session: httpx.Client, headers: dict[str, str] | None = None
) -> UsageWindow:
    response = session.get(f"{GITHUB_API_URL}/copilot_internal/user", headers=headers)
    response.raise_for_status()
    return parse_copilot_internal(response.json())


def parse_copilot_usage(payload: dict[str, Any]) -> float:
    usage_items = payload.get("usageItems") or []
    if usage_items:
        return sum(
            _coerce_number(item.get("grossQuantity"))
            for item in usage_items
            if item.get("product") == "Copilot"
        )
    return _coerce_number(payload.get("grossQuantity"))


def parse_copilot_internal(payload: dict[str, Any]) -> UsageWindow:
    snapshots = payload.get("quota_snapshots") or {}
    premium = snapshots.get("premium_interactions") or {}
    entitlement = _coerce_number(premium.get("entitlement"))
    remaining = _coerce_number(premium.get("remaining"))
    unlimited = bool(premium.get("unlimited"))
    reset_at = parse_timestamp(
        payload.get("quota_reset_date") or payload.get("quota_reset_date_utc")
    )

    label = "Requests"
    if unlimited or entitlement <= 0:
        return UsageWindow(
            label=label,
            used_percent=0.0,
            reset_at=reset_at,
        )

    used = max(entitlement - remaining, 0.0)
    used_percent = (used / entitlement) * 100.0 if entitlement else 0.0
    return UsageWindow(
        label=label,
        used_percent=used_percent,
        reset_at=reset_at,
        used=used,
        limit=entitlement,
    )


def build_copilot_window(used: float, today: date | None = None) -> UsageWindow:
    current = today or date.today()
    reset_at = _next_month_start(current)
    used_percent = 0.0
    if COPILOT_PRO_MONTHLY_LIMIT > 0:
        used_percent = used / COPILOT_PRO_MONTHLY_LIMIT * 100.0
    return UsageWindow(
        label="monthly",
        used_percent=used_percent,
        reset_at=reset_at,
        used=used,
        limit=COPILOT_PRO_MONTHLY_LIMIT,
    )


def _next_month_start(current: date) -> datetime:
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _coerce_number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
