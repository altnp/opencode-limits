from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import os
import subprocess

from opencode_limits.cache import DEFAULT_CACHE_TTL_SECONDS
from opencode_limits.models import UsageWindow
from opencode_limits.render import usage_style


def render_tmux_status(
    codex_windows: Iterable[UsageWindow] | None,
    copilot_window: UsageWindow | None,
) -> str:
    codex_list = list(codex_windows or [])
    if not codex_list and copilot_window is None:
        return ""

    five_hour = _find_window(codex_list, "5HR")
    weekly = _find_window(codex_list, "Weekly")

    codex_icon = _styled_icon("", five_hour)
    codex_five = _styled_percent(five_hour)
    codex_weekly = _styled_percent(weekly)

    copilot_icon = _styled_icon("", copilot_window)
    copilot_percent = _styled_percent(copilot_window)

    return f"{codex_icon} {codex_five}/{codex_weekly} {copilot_icon} {copilot_percent}"


@dataclass(frozen=True)
class CacheSettings:
    path: str | None
    ttl_seconds: int
    disabled: bool
    refresh: bool


def load_cache_settings() -> CacheSettings:
    settings = CacheSettings(
        path=None,
        ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
        disabled=False,
        refresh=False,
    )

    tmux_values = _read_tmux_settings()
    settings = _merge_cache_settings(settings, tmux_values)

    env_values = {
        "path": os.environ.get("OPENCODE_LIMITS_CACHE_PATH"),
        "ttl": os.environ.get("OPENCODE_LIMITS_CACHE_TTL"),
        "disable": os.environ.get("OPENCODE_LIMITS_CACHE_DISABLE"),
        "refresh": os.environ.get("OPENCODE_LIMITS_REFRESH"),
    }
    return _merge_cache_settings(settings, env_values)


def _read_tmux_settings() -> dict[str, str | None]:
    if "TMUX" not in os.environ:
        return {}
    return {
        "path": _read_tmux_option("@opencode_limits_cache_path"),
        "ttl": _read_tmux_option("@opencode_limits_cache_ttl"),
        "disable": _read_tmux_option("@opencode_limits_cache_disable"),
        "refresh": _read_tmux_option("@opencode_limits_refresh"),
    }


def _read_tmux_option(option: str) -> str | None:
    try:
        result = subprocess.run(
            ["tmux", "show-option", "-gqv", option],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _merge_cache_settings(
    current: CacheSettings, incoming: dict[str, str | None]
) -> CacheSettings:
    path = incoming.get("path") or current.path
    ttl_value = incoming.get("ttl")
    ttl_seconds = _parse_int(ttl_value, current.ttl_seconds)
    disable_value = incoming.get("disable")
    refresh_value = incoming.get("refresh")
    disabled = _parse_bool(disable_value, current.disabled)
    refresh = _parse_bool(refresh_value, current.refresh)
    return CacheSettings(
        path=path,
        ttl_seconds=ttl_seconds,
        disabled=disabled,
        refresh=refresh,
    )


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _find_window(
    windows: Iterable[UsageWindow],
    label: str,
) -> UsageWindow | None:
    target = label.strip().lower()
    for window in windows:
        if window.label.strip().lower() == target:
            return window
    return None


def _styled_icon(icon: str, window: UsageWindow | None) -> str:
    if window is None:
        return icon
    percent = _clamp_percent(window.used_percent)
    return _style_text(icon, usage_style(percent))


def _styled_percent(window: UsageWindow | None) -> str:
    if window is None:
        return "--%"
    percent = _clamp_percent(window.used_percent)
    value = f"{int(round(percent))}%"
    return _style_text(value, usage_style(percent))


def _clamp_percent(percent: float) -> float:
    return max(0.0, min(100.0, percent))


def _style_text(text: str, color: str) -> str:
    return f"#[fg={color}]{text}#[default]"
