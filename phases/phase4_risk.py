"""Phase 4: parallel risk analyst positions + Portfolio Manager final decision.

Round 1: all three risk analysts run in parallel (no prior cross-responses yet).
Subsequent rounds (if max_risk_discuss_rounds > 1): sequential, each analyst
reads the previous round's peer responses.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from agent import read_report
from agents.managers import run_portfolio_manager
from agents.risk import (
    run_aggressive_analyst,
    run_conservative_analyst,
    run_neutral_analyst,
)
from config import Config


async def run_phase4(
    ticker: str,
    trade_date: str,
    report_paths: dict[str, Path],
    trader_plan_path: Path,
    investment_plan_path: Path,
    past_context: str,
    cfg: Config,
) -> Path:
    """Run risk debate then Portfolio Manager. Returns final_trade_decision path."""
    risk_dir = cfg.reports_dir / ticker / "risk"
    risk_dir.mkdir(parents=True, exist_ok=True)

    market_report = read_report(report_paths["market"])
    sentiment_report = read_report(report_paths["sentiment"])
    news_report = read_report(report_paths["news"])
    fundamentals_report = read_report(report_paths["fundamentals"])
    trader_decision = read_report(trader_plan_path)

    history = ""
    last_agg = ""
    last_con = ""
    last_neu = ""

    for round_n in range(1, cfg.max_risk_discuss_rounds + 1):
        agg_path = risk_dir / f"round-{round_n:02d}-aggressive.md"
        con_path = risk_dir / f"round-{round_n:02d}-conservative.md"
        neu_path = risk_dir / f"round-{round_n:02d}-neutral.md"

        if round_n == 1:
            # Parallel: all three produce initial positions independently
            coros = []
            if not agg_path.exists():
                coros.append(run_aggressive_analyst(
                    ticker=ticker, trade_date=trade_date, out_path=agg_path,
                    trader_decision=trader_decision,
                    market_report=market_report, sentiment_report=sentiment_report,
                    news_report=news_report, fundamentals_report=fundamentals_report,
                    history=history, last_conservative="", last_neutral="",
                    cfg=cfg,
                ))
            if not con_path.exists():
                coros.append(run_conservative_analyst(
                    ticker=ticker, trade_date=trade_date, out_path=con_path,
                    trader_decision=trader_decision,
                    market_report=market_report, sentiment_report=sentiment_report,
                    news_report=news_report, fundamentals_report=fundamentals_report,
                    history=history, last_aggressive="", last_neutral="",
                    cfg=cfg,
                ))
            if not neu_path.exists():
                coros.append(run_neutral_analyst(
                    ticker=ticker, trade_date=trade_date, out_path=neu_path,
                    trader_decision=trader_decision,
                    market_report=market_report, sentiment_report=sentiment_report,
                    news_report=news_report, fundamentals_report=fundamentals_report,
                    history=history, last_aggressive="", last_conservative="",
                    cfg=cfg,
                ))
            if coros:
                await asyncio.gather(*coros)
            last_agg = read_report(agg_path)
            last_con = read_report(con_path)
            last_neu = read_report(neu_path)
            history += f"\n{last_agg}\n{last_con}\n{last_neu}"
        else:
            # Sequential cross-rebuttal for rounds > 1
            await run_aggressive_analyst(
                ticker=ticker, trade_date=trade_date, out_path=agg_path,
                trader_decision=trader_decision,
                market_report=market_report, sentiment_report=sentiment_report,
                news_report=news_report, fundamentals_report=fundamentals_report,
                history=history, last_conservative=last_con, last_neutral=last_neu,
                cfg=cfg,
            )
            last_agg = read_report(agg_path)
            history += f"\n{last_agg}"

            await run_conservative_analyst(
                ticker=ticker, trade_date=trade_date, out_path=con_path,
                trader_decision=trader_decision,
                market_report=market_report, sentiment_report=sentiment_report,
                news_report=news_report, fundamentals_report=fundamentals_report,
                history=history, last_aggressive=last_agg, last_neutral=last_neu,
                cfg=cfg,
            )
            last_con = read_report(con_path)
            history += f"\n{last_con}"

            await run_neutral_analyst(
                ticker=ticker, trade_date=trade_date, out_path=neu_path,
                trader_decision=trader_decision,
                market_report=market_report, sentiment_report=sentiment_report,
                news_report=news_report, fundamentals_report=fundamentals_report,
                history=history, last_aggressive=last_agg, last_conservative=last_con,
                cfg=cfg,
            )
            last_neu = read_report(neu_path)
            history += f"\n{last_neu}"

    risk_debate_history = history
    investment_plan = read_report(investment_plan_path)
    trader_plan = read_report(trader_plan_path)

    out_path = cfg.reports_dir / ticker / "final_trade_decision.md"
    if not out_path.exists():
        await run_portfolio_manager(
            ticker=ticker,
            trade_date=trade_date,
            out_path=out_path,
            risk_debate_history=risk_debate_history,
            research_plan=investment_plan,
            trader_plan=trader_plan,
            past_context=past_context,
            cfg=cfg,
        )
    return out_path
