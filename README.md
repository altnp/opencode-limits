# OpenCode Limits CLI

`opencode-limits` is a small CLI for viewing Codex and GitHub Copilot usage.

## Requirements

- Python 3.10+
- `uv` (recommended) or `pip`

## Install

```bash
git clone https://github.com/altnp/opencode-limits.git
cd opencode-limits
uv venv
uv pip install -e .
```

If you prefer `pip`:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Usage

```bash
opencode-limits
```

The CLI reads `~/.local/share/opencode/auth.json` with keys:

- `openai.access`
- `openai.accountId`
- `github-copilot.access`

Example:

```json
{
  "openai": {
    "access": "...",
    "accountId": "..."
  },
  "github-copilot": {
    "access": "..."
  }
}
```

## Update the Copilot Request Limit

The Copilot billing endpoint does not return plan limits, so the CLI uses a
constant. Update `COPILOT_PRO_MONTHLY_LIMIT` in
`src/opencode_limits/providers/copilot.py` to match your plan.

## Development

```bash
uv run python -m pytest
```
