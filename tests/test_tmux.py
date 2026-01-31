from opencode_limits.models import UsageWindow
from opencode_limits.tmux import render_tmux_status


def test_tmux_percent_clamp_and_fallback() -> None:
    codex_windows = [UsageWindow(label="5HR", used_percent=120.4, reset_at=None)]

    output = render_tmux_status(codex_windows, None)

    assert output == "#[fg=red]#[default] #[fg=red]100%#[default]/--%  --%"


def test_tmux_color_mapping() -> None:
    codex_windows = [
        UsageWindow(label="5HR", used_percent=50.0, reset_at=None),
        UsageWindow(label="Weekly", used_percent=85.0, reset_at=None),
    ]
    copilot_window = UsageWindow(label="monthly", used_percent=99.0, reset_at=None)

    output = render_tmux_status(codex_windows, copilot_window)

    assert (
        output
        == "#[fg=cyan]#[default] #[fg=cyan]50%#[default]/#[fg=yellow]85%#[default] "
        "#[fg=red]#[default] #[fg=red]99%#[default]"
    )


def test_tmux_missing_codex_windows() -> None:
    copilot_window = UsageWindow(label="monthly", used_percent=55.0, reset_at=None)

    output = render_tmux_status([], copilot_window)

    assert output == " --%/--% #[fg=cyan]#[default] #[fg=cyan]55%#[default]"
