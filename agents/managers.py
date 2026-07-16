"""Research Manager and Portfolio Manager agents."""
from __future__ import annotations

from pathlib import Path

from agent import instrument_context, run_agent, write_report
from config import Config


async def run_research_manager(
    ticker: str,
    trade_date: str,
    out_path: Path,
    debate_history: str,
    cfg: Config,
) -> Path:
    """Judges the bull/bear debate and produces an investment plan."""
    prompt = (
        f"As the Research Manager and debate facilitator, your role is to critically evaluate"
        f" this round of debate and deliver a clear, actionable investment plan for the trader.\n\n"
        f"{instrument_context(ticker)}\n\n"
        f"---\n\n"
        f"**Rating Scale** (use exactly one):\n"
        f"- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position\n"
        f"- **Overweight**: Constructive view; recommend gradually increasing exposure\n"
        f"- **Hold**: Balanced view; recommend maintaining the current position\n"
        f"- **Underweight**: Cautious view; recommend trimming exposure\n"
        f"- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position\n\n"
        f"Commit to a clear stance whenever the debate's strongest arguments warrant one;"
        f" reserve Hold for situations where the evidence on both sides is genuinely balanced.\n\n"
        f"---\n\n"
        f"**Debate History:**\n{debate_history}\n\n"
        f"---\n\n"
        f"Produce your investment plan using exactly these fields:\n\n"
        f"**Recommendation**: <one of Buy/Overweight/Hold/Underweight/Sell>\n\n"
        f"**Rationale**: <conversational summary of which arguments carried the debate>\n\n"
        f"**Strategic Actions**: <concrete steps for the trader to implement the recommendation>\n\n"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are the Research Manager. Synthesise the bull/bear debate into a clear, decisive investment plan.",
        model=cfg.deep_model,
        name="research-manager",
    )
    write_report(out_path, "Research Manager: Investment Plan", ticker, trade_date, content)
    return out_path


async def run_portfolio_manager(
    ticker: str,
    trade_date: str,
    out_path: Path,
    risk_debate_history: str,
    research_plan: str,
    trader_plan: str,
    past_context: str,
    cfg: Config,
) -> Path:
    """Synthesises the risk debate into the final PortfolioDecision."""
    lessons_line = (
        f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
        if past_context
        else ""
    )

    pm_rating_scale = (
        "**Rating Scale** (use exactly one):\n"
        "- **Buy**: Strong conviction to enter or add to position\n"
        "- **Overweight**: Favorable outlook, gradually increase exposure\n"
        "- **Hold**: Maintain current position, no action needed\n"
        "- **Underweight**: Reduce exposure, take partial profits\n"
        "- **Sell**: Exit position or avoid entry"
    )

    prompt = (
        f"As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final"
        f" trading decision.\n\n"
        f"{instrument_context(ticker)}\n\n"
        f"---\n\n"
        f"{pm_rating_scale}\n\n"
        f"**Context:**\n"
        f"- Research Manager's investment plan: **{research_plan}**\n"
        f"- Trader's transaction proposal: **{trader_plan}**\n"
        f"{lessons_line}"
        f"**Risk Analysts Debate History:**\n{risk_debate_history}\n\n"
        f"---\n\n"
        f"Be decisive and ground every conclusion in specific evidence from the analysts.\n\n"
        f"Produce your final decision using exactly these fields:\n\n"
        f"**Rating**: <one of Buy/Overweight/Hold/Underweight/Sell>\n\n"
        f"**Executive Summary**: <concise action plan: entry strategy, position sizing, key risk"
        f" levels, time horizon — two to four sentences>\n\n"
        f"**Investment Thesis**: <detailed reasoning anchored in specific evidence from the"
        f" analysts' debate>\n\n"
        f"**Price Target**: <optional target price>\n\n"
        f"**Time Horizon**: <optional recommended holding period>\n\n"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are the Portfolio Manager. Deliver a decisive, evidence-grounded final trade decision.",
        model=cfg.epic_model,
        name="portfolio-manager",
    )
    write_report(out_path, "Portfolio Manager: Final Trade Decision", ticker, trade_date, content)
    return out_path
