from datetime import datetime, timezone

from opencode_limits.providers import codex


def test_parse_codex_usage() -> None:
    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 42,
                "reset_at": "2026-01-25T10:00:00Z",
            },
            "secondary_window": {
                "used_percent": 10,
                "reset_at": "2026-01-29T10:00:00Z",
            },
        },
        "code_review_rate_limit": [
            {
                "window": "weekly",
                "used_percent": 12.5,
                "reset_at": "2026-01-28T00:00:00Z",
            }
        ],
    }

    windows = codex.parse_codex_usage(payload)

    assert [window.label for window in windows] == ["5HR", "Weekly"]
    assert windows[0].used_percent == 42.0
    assert windows[0].reset_at == datetime(2026, 1, 25, 10, 0, tzinfo=timezone.utc)
