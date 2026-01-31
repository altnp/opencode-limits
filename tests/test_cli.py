from opencode_limits import cli
from opencode_limits.auth import AuthTokens
from opencode_limits.models import UsageWindow
import httpx


def test_main_returns_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "load_auth",
        lambda: AuthTokens(
            openai="token",
            github_copilot="token",
            chatgpt_account_id="account",
        ),
    )
    monkeypatch.setattr(
        cli,
        "fetch_codex_usage",
        lambda tokens: [
            UsageWindow(label="5h window", used_percent=0.0, reset_at=None)
        ],
    )
    monkeypatch.setattr(
        cli,
        "fetch_copilot_usage",
        lambda tokens: UsageWindow(label="monthly", used_percent=0.0, reset_at=None),
    )

    assert cli.main([]) == 0


def test_main_returns_zero_when_one_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "load_auth",
        lambda: AuthTokens(
            openai="token",
            github_copilot="token",
            chatgpt_account_id="account",
        ),
    )
    monkeypatch.setattr(
        cli,
        "fetch_codex_usage",
        lambda tokens: [
            UsageWindow(label="5h window", used_percent=0.0, reset_at=None)
        ],
    )

    def _raise_error(tokens):
        raise httpx.HTTPError("copilot failed")

    monkeypatch.setattr(cli, "fetch_copilot_usage", _raise_error)

    assert cli.main([]) == 0


def test_main_tmux_outputs_status(monkeypatch, capsys) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("OPENCODE_LIMITS_CACHE_DISABLE", "1")
    monkeypatch.setattr(
        cli,
        "load_auth",
        lambda: AuthTokens(
            openai="token",
            github_copilot="token",
            chatgpt_account_id="account",
        ),
    )
    monkeypatch.setattr(
        cli,
        "fetch_codex_usage",
        lambda tokens: [
            UsageWindow(label="5HR", used_percent=10.0, reset_at=None),
            UsageWindow(label="Weekly", used_percent=20.0, reset_at=None),
        ],
    )
    monkeypatch.setattr(
        cli,
        "fetch_copilot_usage",
        lambda tokens: UsageWindow(label="monthly", used_percent=85.0, reset_at=None),
    )

    assert cli.main(["--tmux"]) == 0

    output = capsys.readouterr().out
    assert (
        output
        == "#[fg=cyan]#[default] #[fg=cyan]10%#[default]/#[fg=cyan]20%#[default] "
        "#[fg=yellow]#[default] #[fg=yellow]85%#[default]"
    )


def test_main_tmux_returns_one_without_data(monkeypatch) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("OPENCODE_LIMITS_CACHE_DISABLE", "1")
    monkeypatch.setattr(
        cli,
        "load_auth",
        lambda: AuthTokens(
            openai="token",
            github_copilot="token",
            chatgpt_account_id="account",
        ),
    )
    monkeypatch.setattr(cli, "fetch_codex_usage", lambda tokens: [])
    monkeypatch.setattr(cli, "fetch_copilot_usage", lambda tokens: None)

    assert cli.main(["--tmux"]) == 1
