from __future__ import annotations

from rich.console import Console
from rich.text import Text

from opencode_limits.models import UsageWindow


def render_sections(
    console: Console,
    sections: list[tuple[str, list[UsageWindow]]],
) -> None:
    all_windows = [window for _, windows in sections for window in windows]
    if not all_windows:
        return

    label_width = max(len(window.label) for window in all_windows)
    usage_width = max(len(format_usage_suffix(window)) for window in all_windows)

    for index, (title, windows) in enumerate(sections):
        if index:
            console.print()
        if console.is_terminal:
            console.print(Text(title, style="bold magenta"))
        else:
            console.print(title)
        if not windows:
            continue
        for window in windows:
            percent = max(0.0, min(100.0, window.used_percent))
            reset_text = format_reset(window)
            label_text = window.label.ljust(label_width)
            percent_text = f"{percent:>3.0f}%"
            usage_text = format_usage_suffix(window).rjust(usage_width)
            if console.is_terminal:
                bar = _bar_text(percent)
                line = Text(f"{label_text} ")
                line.append(bar)
                line.append(" ")
                line.append(Text(percent_text, style=usage_style(percent)))
                if usage_width:
                    line.append(" ")
                    line.append(usage_text)
                line.append(" Resets: ")
                line.append(reset_text)
                console.print(line)
            else:
                bar = _bar_string(percent)
                line = f"{label_text} {bar} {percent_text}"
                if usage_width:
                    line += f" {usage_text}"
                line += f" Resets: {reset_text}"
                console.print(line)


def format_reset(window: UsageWindow) -> str:
    if window.reset_at is None:
        return "n/a"
    return window.reset_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _bar_string(percent: float, width: int = 28) -> str:
    filled = int(round(width * percent / 100.0))
    filled = max(0, min(width, filled))
    return f"[{'#' * filled}{'-' * (width - filled)}]"


def _bar_text(percent: float, width: int = 28) -> Text:
    filled = int(round(width * percent / 100.0))
    filled = max(0, min(width, filled))
    text = Text("[")
    if filled:
        text.append("#" * filled, style=usage_style(percent))
    if width - filled:
        text.append("-" * (width - filled), style="bright_black")
    text.append("]")
    return text


def usage_style(percent: float) -> str:
    if percent >= 99:
        return "red"
    if percent > 80:
        return "yellow"
    return "cyan"


def format_usage_suffix(window: UsageWindow) -> str:
    if window.used is None or window.limit is None:
        return ""
    return f"{window.used:.0f}/{window.limit:.0f}"
