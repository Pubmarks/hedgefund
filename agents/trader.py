"""Trader agent — Phase 3."""
from __future__ import annotations

from pathlib import Path

from agent import instrument_context, run_agent, write_report
from config import Config


async def run_trader(
    ticker: str,
    trade_date: str,
    out_path: Path,
    investment_plan: str,
    cfg: Config,
) -> Path:
    """Converts the Research Manager's investment plan into a concrete TraderProposal."""
    prompt = (
        f"Based on a comprehensive analysis by a team of analysts, here is an investment plan"
        f" tailored for {ticker}. {instrument_context(ticker)} This plan incorporates insights"
        f" from current technical market trends, macroeconomic indicators, and social media"
        f" sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\n"
        f"Proposed Investment Plan: {investment_plan}\n\n"
        f"Leverage these insights to make an informed and strategic decision.\n\n"
        f"Produce your trader proposal using exactly these fields:\n\n"
        f"**Action**: <one of Buy/Hold/Sell>\n\n"
        f"**Reasoning**: <the case for this action, anchored in the analysts' reports and the"
        f" research plan — two to four sentences>\n\n"
        f"**Entry Price**: <optional entry price target>\n\n"
        f"**Stop Loss**: <optional stop-loss price>\n\n"
        f"**Position Sizing**: <optional sizing guidance, e.g. '5% of portfolio'>\n\n"
        f"End with the mandatory line:\n"
        f"FINAL TRANSACTION PROPOSAL: **BUY** (or HOLD or SELL, uppercase, matching Action)\n\n"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=(
            "You are a trading agent analyzing market data to make investment decisions."
            " Based on your analysis, provide a specific recommendation to buy, sell, or hold."
            " Anchor your reasoning in the analysts' reports and the research plan."
        ),
        model=cfg.deep_model,
        name="trader",
    )
    write_report(out_path, "Trader Proposal", ticker, trade_date, content)
    return out_path
