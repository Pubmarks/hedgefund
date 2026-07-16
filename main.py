"""Ticker company research via Pubmarks tools + OpenCode.

Fetches company data with `tools.fundamentals.fetch_fundamentals`, then asks
OpenCode to write a short markdown summary (no web fetch).

Defaults to subprocess ACP (`opencode acp`) via opencode-agent-sdk.
Set OPENCODE_SERVER_URL to use an external `opencode serve`.

Run with uv:
    uv run --frozen python main.py AAPL
    uv run --frozen python main.py AAPL -o summary.md

The markdown body is always written to a file. Stdout only reports the path.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from agent import ensure_opencode_ready, run_agent
from config import REPO_ROOT, default_config
from tools.fundamentals import fetch_fundamentals

# Prefer a local cache when running outside the container default (/data/cache).
os.environ.setdefault("TOOLS_CACHE_DIR", str(REPO_ROOT / ".cache"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Look up a ticker with tools.fundamentals and summarize the company.",
    )
    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g. AAPL)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Markdown output path (default: out/<TICKER>.md)",
    )
    return parser.parse_args(argv)


def _fundamentals_text(ticker: str) -> str:
    result = fetch_fundamentals(ticker)
    artifacts = result.get("artifacts") or []
    chunks = [
        str(art.get("content", "")).strip()
        for art in artifacts
        if art.get("content")
    ]
    body = "\n\n".join(chunks).strip()
    if not body:
        summary = str(result.get("summary") or "").strip()
        if summary:
            return summary
        raise RuntimeError(f"empty fundamentals result for {ticker}")
    return body


def _prompt(ticker: str, fundamentals: str) -> str:
    return (
        f"Using only the fundamentals data below, write a short markdown summary "
        f"for ticker {ticker}.\n"
        "Include:\n"
        f"- The company name the ticker {ticker} belongs to\n"
        "- What you can infer about the business from the available fields "
        "(2–4 sentences; say if detail is limited)\n"
        "- Sector / industry if available\n"
        "- A few key fundamentals (market cap, valuation, margins) when present\n"
        "Keep it concise. Output markdown only — no preamble.\n\n"
        f"--- fundamentals ---\n{fundamentals}\n--- end ---"
    )


SYSTEM = (
    "You are a concise equity research assistant. Summarize only from the "
    "provided fundamentals data. Do not invent facts or fetch the web."
)


async def research_ticker(ticker: str) -> str:
    fundamentals = _fundamentals_text(ticker)
    cfg = default_config()
    await ensure_opencode_ready(server_url=cfg.opencode_server_url)
    return await run_agent(
        prompt=_prompt(ticker, fundamentals),
        system_prompt=SYSTEM,
        allowed_tools=(),
        max_turns=1,
        model=cfg.quick_model,
        name=f"ticker-{ticker}",
    )


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ticker = args.ticker.strip().upper()
    if not ticker:
        raise SystemExit("error: ticker must be non-empty")

    text = await research_ticker(ticker)
    summary = text.strip()
    if not summary:
        raise SystemExit(f"error: empty summary for {ticker}")

    # Ensure a clear title for Action summaries / artifacts.
    if not summary.lstrip().startswith("#"):
        summary = f"# {ticker}\n\n{summary}"

    output = args.output if args.output is not None else Path("out") / f"{ticker}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(summary + "\n", encoding="utf-8")
    print(f"wrote {output} ({output.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
