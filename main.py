"""Multi-agent ticker research pipeline.

Runs a full 4-phase analysis (analysts, debate, trader, risk) and writes
the stitched result to a single markdown file.

Defaults to subprocess ACP (`opencode acp`) via opencode-agent-sdk.
Set OPENCODE_SERVER_URL to use an external `opencode serve`.

Run with uv:
    uv run --frozen python main.py AAPL
    uv run --frozen python main.py AAPL -o summary.md
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from config import REPO_ROOT, default_config
from pipeline import research

# Prefer a local cache when running outside the container default (/data/cache).
os.environ.setdefault("TOOLS_CACHE_DIR", str(REPO_ROOT / ".cache"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-agent hedge fund research pipeline for a ticker.",
    )
    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g. AAPL)",
    )
    parser.add_argument(
        "-d",
        "--date",
        default=None,
        help="Trade date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Markdown output path (default: out/<TICKER>/final-report.md)",
    )
    parser.add_argument(
        "--debate-rounds",
        type=int,
        default=1,
        help="Bull/Bear debate rounds (default: 1)",
    )
    parser.add_argument(
        "--risk-rounds",
        type=int,
        default=1,
        help="Risk analyst discussion rounds (default: 1)",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ticker = args.ticker.strip().upper()
    if not ticker:
        raise SystemExit("error: ticker must be non-empty")

    cfg = default_config()
    cfg.max_debate_rounds = args.debate_rounds
    cfg.max_risk_discuss_rounds = args.risk_rounds

    trade_date = args.date or date.today().isoformat()

    rating = await research(ticker, trade_date, cfg)

    final_report = cfg.reports_dir / ticker / "final-report.md"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        content = final_report.read_text(encoding="utf-8")
        args.output.write_text(content, encoding="utf-8")
        final_report = args.output

    print(f"\nFinal rating:  {rating}")
    print(f"Report (md):   {final_report}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
