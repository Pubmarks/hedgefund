"""Phase 2: sequential bull/bear debate + Research Manager judgment."""
from __future__ import annotations

from pathlib import Path

from agent import read_report
from agents.managers import run_research_manager
from agents.researchers import run_bear_researcher, run_bull_researcher
from config import Config


async def run_phase2(
    ticker: str,
    trade_date: str,
    report_paths: dict[str, Path],
    cfg: Config,
) -> Path:
    """Run bull/bear debate for N rounds, then Research Manager. Returns debate path."""
    debate_dir = cfg.reports_dir / ticker / "debate"
    debate_dir.mkdir(parents=True, exist_ok=True)

    market_report = read_report(report_paths["market"])
    sentiment_report = read_report(report_paths["sentiment"])
    news_report = read_report(report_paths["news"])
    fundamentals_report = read_report(report_paths["fundamentals"])

    debate_history = ""
    last_bull = ""
    last_bear = ""

    for round_n in range(1, cfg.max_debate_rounds + 1):
        bull_path = debate_dir / f"round-{round_n:02d}-bull.md"
        bear_path = debate_dir / f"round-{round_n:02d}-bear.md"

        if not bull_path.exists():
            await run_bull_researcher(
                ticker=ticker,
                trade_date=trade_date,
                out_path=bull_path,
                market_report=market_report,
                sentiment_report=sentiment_report,
                news_report=news_report,
                fundamentals_report=fundamentals_report,
                debate_history=debate_history,
                last_bear_argument=last_bear,
                cfg=cfg,
            )
        last_bull = read_report(bull_path)
        debate_history += f"\n{last_bull}"

        if not bear_path.exists():
            await run_bear_researcher(
                ticker=ticker,
                trade_date=trade_date,
                out_path=bear_path,
                market_report=market_report,
                sentiment_report=sentiment_report,
                news_report=news_report,
                fundamentals_report=fundamentals_report,
                debate_history=debate_history,
                last_bull_argument=last_bull,
                cfg=cfg,
            )
        last_bear = read_report(bear_path)
        debate_history += f"\n{last_bear}"

    debate_path = cfg.reports_dir / ticker / "debate.md"
    if not debate_path.exists():
        await run_research_manager(
            ticker=ticker,
            trade_date=trade_date,
            out_path=debate_path,
            debate_history=debate_history,
            cfg=cfg,
        )
    return debate_path
