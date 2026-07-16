"""Minimal OpenCode SDK example using the built-in webfetch tool.

Defaults to subprocess ACP (`opencode acp`) via opencode-agent-sdk, matching
Sniper-Street. Set OPENCODE_SERVER_URL to use an external `opencode serve`.

Run with uv:
    uv run --frozen python main.py
"""

from __future__ import annotations

import asyncio
import sys

from agent import ensure_opencode_ready, run_agent
from config import default_config

PROMPT = (
    "Fetch https://modelcontextprotocol.io and summarize what it is "
    "in 3 short bullet points."
)

SYSTEM = (
    "You are a concise research assistant. Use webfetch to read the URL, "
    "then answer with exactly 3 short bullet points."
)


async def main() -> None:
    cfg = default_config()
    await ensure_opencode_ready(server_url=cfg.opencode_server_url)
    text = await run_agent(
        prompt=PROMPT,
        system_prompt=SYSTEM,
        allowed_tools=("WebFetch",),
        max_turns=5,
        model=cfg.quick_model,
        name="webfetch-demo",
    )
    print(text)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
