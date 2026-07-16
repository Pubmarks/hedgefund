"""Phase 1: parallel fan-out of all four analyst agents."""
from __future__ import annotations

import asyncio
from pathlib import Path

from agents.analysts import (
    run_fundamentals_analyst,
    run_global_news_summarizer,
    run_macro_web_researcher,
    run_market_analyst,
    run_news_analyst,
    run_social_analyst,
)
from config import Config


async def run_phase1(ticker: str, trade_date: str, cfg: Config) -> dict[str, Path]:
    """Run all four analysts in parallel. Returns paths keyed by report name."""
    # Global context steps run once per freshness window, before per-ticker analysts.
    await asyncio.gather(
        run_global_news_summarizer(trade_date, cfg),
        run_macro_web_researcher(trade_date, cfg),
    )

    base = cfg.reports_dir / ticker
    base.mkdir(parents=True, exist_ok=True)
    specs = [
        ("market",       base / "market.md",
         lambda: run_market_analyst(ticker, trade_date, cfg)),
        ("sentiment",    base / "sentiment.md",
         lambda: run_social_analyst(ticker, trade_date, cfg)),
        ("news",         base / "news.md",
         lambda: run_news_analyst(ticker, trade_date, cfg)),
        ("fundamentals", base / "fundamentals.md",
         lambda: run_fundamentals_analyst(ticker, trade_date, cfg)),
    ]
    pending_keys, pending_coros, skipped = [], [], {}
    for key, path, make_coro in specs:
        if path.exists():
            skipped[key] = path
        else:
            pending_keys.append(key)
            pending_coros.append(make_coro())

    results = await asyncio.gather(*pending_coros)
    paths = {**skipped, **dict(zip(pending_keys, results))}
    return {k: paths[k] for k, _, _ in specs}
