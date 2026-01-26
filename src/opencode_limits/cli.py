from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Sequence

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from opencode_limits.auth import AuthError, AuthTokens, load_auth
from opencode_limits.models import UsageWindow
from opencode_limits.providers.codex import fetch_codex_usage
from opencode_limits.providers.copilot import fetch_copilot_usage
from opencode_limits.render import render_sections


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="opencode-limits",
        description="Show usage limits for Codex and GitHub Copilot.",
    )
    parser.parse_args(argv)

    console = Console()
    try:
        tokens = load_auth()
    except AuthError as exc:
        _print_error(console, str(exc))
        return 1

    codex_windows, copilot_window, failures = _fetch_usage(console, tokens)

    sections: list[tuple[str, list[UsageWindow]]] = []
    if codex_windows:
        sections.append(("Codex", codex_windows))
    if copilot_window is not None:
        sections.append(("GitHub Copilot", [copilot_window]))
    if sections:
        render_sections(console, sections)

    for message in failures:
        _print_error(console, message)

    if not codex_windows and copilot_window is None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _print_error(console: Console, message: str) -> None:
    if console.is_terminal:
        console.print(f"[red]{message}[/red]")
    else:
        console.print(message)


def _fetch_usage(
    console: Console,
    tokens: AuthTokens,
) -> tuple[list[UsageWindow], UsageWindow | None, list[str]]:
    codex_windows: list[UsageWindow] = []
    copilot_window: UsageWindow | None = None
    failures: list[str] = []

    def store_result(name: str, result) -> None:
        nonlocal codex_windows, copilot_window
        if name == "Codex":
            codex_windows = result
        else:
            copilot_window = result

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_map = {
            executor.submit(fetch_codex_usage, tokens): "Codex",
            executor.submit(fetch_copilot_usage, tokens): "GitHub Copilot",
        }

        if console.is_terminal:
            progress = Progress(
                SpinnerColumn(finished_text="✔"),
                TextColumn("{task.description}"),
                transient=False,
            )
            task_ids = {
                name: progress.add_task(name, total=1) for name in future_map.values()
            }
            with progress:
                while future_map:
                    done, _ = wait(future_map, timeout=0.1, return_when=FIRST_COMPLETED)
                    for future in done:
                        name = future_map.pop(future)
                        task_id = task_ids[name]
                        try:
                            result = future.result()
                        except (httpx.HTTPError, RuntimeError) as exc:
                            failures.append(f"{name} failed: {exc}")
                            progress.update(task_id, completed=1)
                        else:
                            store_result(name, result)
                            progress.update(task_id, completed=1)
        else:
            for future, name in list(future_map.items()):
                try:
                    result = future.result()
                except (httpx.HTTPError, RuntimeError) as exc:
                    failures.append(f"{name} failed: {exc}")
                else:
                    store_result(name, result)

    return codex_windows, copilot_window, failures
