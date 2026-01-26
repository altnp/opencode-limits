from datetime import date, datetime, timezone

from opencode_limits.providers import copilot


def test_parse_copilot_usage_aggregates_items() -> None:
    payload = {
        "usageItems": [
            {"grossQuantity": 120, "product": "Copilot"},
            {"grossQuantity": 30, "product": "Copilot"},
            {"grossQuantity": 15, "product": "Codespaces"},
        ]
    }

    used = copilot.parse_copilot_usage(payload)
    window = copilot.build_copilot_window(used, today=date(2026, 1, 25))

    assert used == 150.0
    assert window.used_percent == 50.0
    assert window.reset_at == datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_parse_copilot_internal_usage() -> None:
    payload = {
        "quota_snapshots": {
            "premium_interactions": {
                "entitlement": 50,
                "remaining": 20,
                "unlimited": False,
            }
        },
        "quota_reset_date": "2026-02-15T00:00:00Z",
    }

    window = copilot.parse_copilot_internal(payload)

    assert window.label == "Requests"
    assert window.used == 30.0
    assert window.limit == 50.0
    assert window.used_percent == 60.0
    assert window.reset_at == datetime(2026, 2, 15, tzinfo=timezone.utc)
