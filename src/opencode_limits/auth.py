from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AUTH_PATH = Path("~/.local/share/opencode/auth.json").expanduser()


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthTokens:
    openai: str
    github_copilot: str
    chatgpt_account_id: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise AuthError(f"Auth file not found at {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuthError(f"Auth file at {path} is not valid JSON") from exc


def load_auth(path: Path | None = None) -> AuthTokens:
    auth_path = path or AUTH_PATH
    data = _load_json(auth_path)

    openai_token, account_id = _extract_openai(data)
    github_copilot = _extract_token(data.get("github-copilot"))

    missing = []
    if not openai_token:
        missing.append("openai.access")
    if not github_copilot:
        missing.append("github-copilot.access")
    if not account_id:
        missing.append("openai.accountId")
    if missing:
        missing_text = ", ".join(missing)
        raise AuthError(f"Auth file missing required keys: {missing_text}")

    return AuthTokens(
        openai=str(openai_token),
        github_copilot=str(github_copilot),
        chatgpt_account_id=str(account_id),
    )


def _extract_openai(data: dict[str, Any]) -> tuple[str | None, str | None]:
    openai_value = data.get("openai")
    if isinstance(openai_value, dict):
        token = _extract_token(openai_value)
        account_id = openai_value.get("accountId")
        return _string_or_none(token), _string_or_none(account_id)
    return _string_or_none(openai_value), _string_or_none(
        data.get("chatgpt-account-id")
    )


def _extract_token(value: Any) -> str | None:
    if isinstance(value, dict):
        token = value.get("access") or value.get("accessToken") or value.get("token")
        return _string_or_none(token)
    return _string_or_none(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
