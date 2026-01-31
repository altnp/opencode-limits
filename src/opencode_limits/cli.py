from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Sequence

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from opencode_limits.auth import AuthError, AuthTokens, load_auth
from opencode_limits.cache import (
    STALE_FALLBACK_SECONDS,
    CacheRecord,
    build_auth_fingerprint,
    build_cache_record,
    cache_path,
    is_fresh,
    is_stale_allowed,
    load_cache,
    save_cache,
)
from opencode_limits.models import UsageWindow
from opencode_limits.providers.codex import fetch_codex_usage
from opencode_limits.providers.copilot import fetch_copilot_usage
from opencode_limits.render import render_sections
from opencode_limits.tmux import load_cache_settings, render_tmux_status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="opencode-limits",
        description="Show usage limits for Codex and GitHub Copilot.",
    )
    parser.add_argument(
        "--tmux",
        action="store_true",
        help="Print tmux-ready usage status line.",
    )
    args = parser.parse_args(argv)

    console = Console()
    try:
        tokens = load_auth()
    except AuthError as exc:
        _print_error(console, str(exc))
        return 1

    if args.tmux:
        return _run_tmux(console, tokens)

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
    show_progress: bool = True,
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

        if show_progress and console.is_terminal:
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


def _run_tmux(console: Console, tokens: AuthTokens) -> int:
    settings = load_cache_settings()
    fingerprint = build_auth_fingerprint(tokens)
    record = None
    cache_file = cache_path(settings.path)

    if not settings.disabled and not settings.refresh:
        record = load_cache(cache_file)
        if record and is_fresh(record, settings.ttl_seconds, fingerprint):
            codex_windows, copilot_window = _cached_windows(record)
            status = render_tmux_status(codex_windows, copilot_window)
            if status:
                console.file.write(status)
                return 0
            return 1

    codex_windows, copilot_window, failures = _fetch_usage(
        console, tokens, show_progress=False
    )
    if codex_windows or copilot_window is not None:
        status = render_tmux_status(codex_windows, copilot_window)
        if status:
            if not settings.disabled and not failures:
                record = build_cache_record(codex_windows, copilot_window, tokens)
                save_cache(cache_file, record)
            console.file.write(status)
            return 0

    if not settings.disabled:
        if record is None:
            record = load_cache(cache_file)
        if record and is_stale_allowed(record, STALE_FALLBACK_SECONDS, fingerprint):
            codex_windows, copilot_window = _cached_windows(record)
            status = render_tmux_status(codex_windows, copilot_window)
            if status:
                console.file.write(status)
                return 0

    return 1


def _cached_windows(
    record: CacheRecord,
) -> tuple[list[UsageWindow], UsageWindow | None]:
    codex_windows = [
        UsageWindow(
            label=label,
            used_percent=window.used_percent,
            reset_at=window.reset_at,
        )
        for label, window in record.codex.items()
    ]
    copilot_window = None
    if record.copilot is not None:
        copilot_window = UsageWindow(
            label="Copilot",
            used_percent=record.copilot.used_percent,
            reset_at=record.copilot.reset_at,
        )
    return codex_windows, copilot_window
