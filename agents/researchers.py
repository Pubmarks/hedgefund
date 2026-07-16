"""Bull and Bear researcher agents — Phase 2 debate."""
from __future__ import annotations

from pathlib import Path

from agent import RATING_INSTRUCTION, run_agent, write_report
from config import Config


async def run_bull_researcher(
    ticker: str,
    trade_date: str,
    out_path: Path,
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    debate_history: str,
    last_bear_argument: str,
    cfg: Config,
) -> Path:
    prompt = (
        f"You are a Bull Analyst advocating for investing in the stock. Your task is to build a"
        f" strong, evidence-based case emphasizing growth potential, competitive advantages, and"
        f" positive market indicators. Leverage the provided research and data to address concerns"
        f" and counter bearish arguments effectively.\n\n"
        f"Key points to focus on:\n"
        f"- Growth Potential: Highlight the company's market opportunities, revenue projections,"
        f" and scalability.\n"
        f"- Competitive Advantages: Emphasize factors like unique products, strong branding, or"
        f" dominant market positioning.\n"
        f"- Positive Indicators: Use financial health, industry trends, and recent positive news"
        f" as evidence.\n"
        f"- Bear Counterpoints: Critically analyze the bear argument with specific data and sound"
        f" reasoning, addressing concerns thoroughly and showing why the bull perspective holds"
        f" stronger merit.\n"
        f"- Engagement: Present your argument in a conversational style, engaging directly with"
        f" the bear analyst's points and debating effectively rather than just listing data.\n\n"
        f"Resources available:\n"
        f"Market research report: {market_report}\n"
        f"Social media sentiment report: {sentiment_report}\n"
        f"Latest world affairs news: {news_report}\n"
        f"Company fundamentals report: {fundamentals_report}\n"
        f"Conversation history of the debate: {debate_history}\n"
        f"Last bear argument: {last_bear_argument}\n\n"
        f"Use this information to deliver a compelling bull argument, refute the bear's concerns,"
        f" and engage in a dynamic debate that demonstrates the strengths of the bull position.\n\n"
        f"Prefix your response with 'Bull Analyst: ' then write your argument for {ticker}."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are a helpful AI assistant participating in a structured investment debate.",
        model=cfg.deep_model,
        name="bull-researcher",
    )
    round_n = int(out_path.stem.split("-")[1])
    write_report(out_path, f"Bull Analyst — Round {round_n}", ticker, trade_date, content)
    return out_path


async def run_bear_researcher(
    ticker: str,
    trade_date: str,
    out_path: Path,
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    debate_history: str,
    last_bull_argument: str,
    cfg: Config,
) -> Path:
    prompt = (
        f"You are a Bear Analyst making the case against investing in the stock. Your goal is to"
        f" present a well-reasoned argument emphasizing risks, challenges, and negative indicators."
        f" Leverage the provided research and data to highlight potential downsides and counter"
        f" bullish arguments effectively.\n\n"
        f"Key points to focus on:\n\n"
        f"- Risks and Challenges: Highlight factors like market saturation, financial instability,"
        f" or macroeconomic threats that could hinder the stock's performance.\n"
        f"- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning,"
        f" declining innovation, or threats from competitors.\n"
        f"- Negative Indicators: Use evidence from financial data, market trends, or recent adverse"
        f" news to support your position.\n"
        f"- Bull Counterpoints: Critically analyze the bull argument with specific data and sound"
        f" reasoning, exposing weaknesses or over-optimistic assumptions.\n"
        f"- Engagement: Present your argument in a conversational style, directly engaging with"
        f" the bull analyst's points and debating effectively rather than simply listing facts.\n\n"
        f"Resources available:\n"
        f"Market research report: {market_report}\n"
        f"Social media sentiment report: {sentiment_report}\n"
        f"Latest world affairs news: {news_report}\n"
        f"Company fundamentals report: {fundamentals_report}\n"
        f"Conversation history of the debate: {debate_history}\n"
        f"Last bull argument: {last_bull_argument}\n\n"
        f"Use this information to deliver a compelling bear argument, refute the bull's claims,"
        f" and engage in a dynamic debate that demonstrates the risks and weaknesses of investing"
        f" in the stock.\n\n"
        f"Prefix your response with 'Bear Analyst: ' then write your argument for {ticker}."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are a helpful AI assistant participating in a structured investment debate.",
        model=cfg.deep_model,
        name="bear-researcher",
    )
    round_n = int(out_path.stem.split("-")[1])
    write_report(out_path, f"Bear Analyst — Round {round_n}", ticker, trade_date, content)
    return out_path
