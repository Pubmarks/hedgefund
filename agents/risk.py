"""Risk analyst agents (Aggressive, Conservative, Neutral) — Phase 4."""
from __future__ import annotations

from pathlib import Path

from agent import RATING_INSTRUCTION, run_agent, write_report
from config import Config


async def run_aggressive_analyst(
    ticker: str,
    trade_date: str,
    out_path: Path,
    trader_decision: str,
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    history: str,
    last_conservative: str,
    last_neutral: str,
    cfg: Config,
) -> Path:
    prompt = (
        f"As the Aggressive Risk Analyst, your role is to actively champion high-reward,"
        f" high-risk opportunities, emphasizing bold strategies and competitive advantages."
        f" When evaluating the trader's decision or plan, focus intently on the potential upside,"
        f" growth potential, and innovative benefits — even when these come with elevated risk."
        f" Use the provided market data and sentiment analysis to strengthen your arguments and"
        f" challenge the opposing views. Specifically, respond directly to each point made by the"
        f" conservative and neutral analysts, countering with data-driven rebuttals and persuasive"
        f" reasoning. Highlight where their caution might miss critical opportunities or where"
        f" their assumptions may be overly conservative. Here is the trader's decision:\n\n"
        f"{trader_decision}\n\n"
        f"Your task is to create a compelling case for the trader's decision by questioning and"
        f" critiquing the conservative and neutral stances to demonstrate why your high-reward"
        f" perspective offers the best path forward. Incorporate insights from the following"
        f" sources into your arguments:\n\n"
        f"Market Research Report: {market_report}\n"
        f"Social Media Sentiment Report: {sentiment_report}\n"
        f"Latest World Affairs Report: {news_report}\n"
        f"Company Fundamentals Report: {fundamentals_report}\n"
        f"Here is the current conversation history: {history}"
        f" Here are the last arguments from the conservative analyst: {last_conservative}"
        f" Here are the last arguments from the neutral analyst: {last_neutral}."
        f" If there are no responses from the other viewpoints yet, present your own argument"
        f" based on the available data.\n\n"
        f"Engage actively by addressing any specific concerns raised, refuting the weaknesses in"
        f" their logic, and asserting the benefits of risk-taking to outpace market norms."
        f" Maintain a focus on debating and persuading, not just presenting data. Challenge each"
        f" counterpoint to underscore why a high-risk approach is optimal."
        f" Output conversationally as if you are speaking without any special formatting.\n\n"
        f"Prefix your response with 'Aggressive Analyst: ' then write your argument."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are the Aggressive Risk Analyst in a structured risk review.",
        model=cfg.deep_model,
        name="aggressive-risk",
    )
    round_n = int(out_path.stem.split("-")[1])
    write_report(out_path, f"Aggressive Risk Analyst — Round {round_n}", ticker, trade_date, content)
    return out_path


async def run_conservative_analyst(
    ticker: str,
    trade_date: str,
    out_path: Path,
    trader_decision: str,
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    history: str,
    last_aggressive: str,
    last_neutral: str,
    cfg: Config,
) -> Path:
    prompt = (
        f"As the Conservative Risk Analyst, your primary objective is to protect assets, minimize"
        f" volatility, and ensure steady, reliable growth. You prioritize stability, security, and"
        f" risk mitigation, carefully assessing potential losses, economic downturns, and market"
        f" volatility. When evaluating the trader's decision or plan, critically examine high-risk"
        f" elements, pointing out where the decision may expose the firm to undue risk and where"
        f" more cautious alternatives could secure long-term gains. Here is the trader's"
        f" decision:\n\n"
        f"{trader_decision}\n\n"
        f"Your task is to actively counter the arguments of the Aggressive and Neutral Analysts,"
        f" highlighting where their views may overlook potential threats or fail to prioritize"
        f" sustainability. Respond directly to their points, drawing from the following data"
        f" sources to build a convincing case for a low-risk approach adjustment to the trader's"
        f" decision:\n\n"
        f"Market Research Report: {market_report}\n"
        f"Social Media Sentiment Report: {sentiment_report}\n"
        f"Latest World Affairs Report: {news_report}\n"
        f"Company Fundamentals Report: {fundamentals_report}\n"
        f"Here is the current conversation history: {history}"
        f" Here is the last response from the aggressive analyst: {last_aggressive}"
        f" Here is the last response from the neutral analyst: {last_neutral}."
        f" If there are no responses from the other viewpoints yet, present your own argument"
        f" based on the available data.\n\n"
        f"Engage by questioning their optimism and emphasizing the potential downsides they may"
        f" have overlooked. Address each of their counterpoints to showcase why a conservative"
        f" stance is ultimately the safest path for the firm's assets. Focus on debating and"
        f" critiquing their arguments to demonstrate the strength of a low-risk strategy over their"
        f" approaches. Output conversationally as if you are speaking without any special"
        f" formatting.\n\n"
        f"Prefix your response with 'Conservative Analyst: ' then write your argument."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are the Conservative Risk Analyst in a structured risk review.",
        model=cfg.deep_model,
        name="conservative-risk",
    )
    round_n = int(out_path.stem.split("-")[1])
    write_report(out_path, f"Conservative Risk Analyst — Round {round_n}", ticker, trade_date, content)
    return out_path


async def run_neutral_analyst(
    ticker: str,
    trade_date: str,
    out_path: Path,
    trader_decision: str,
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    history: str,
    last_aggressive: str,
    last_conservative: str,
    cfg: Config,
) -> Path:
    prompt = (
        f"As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing"
        f" both the potential benefits and risks of the trader's decision or plan. You prioritize"
        f" a well-rounded approach, evaluating the upsides and downsides while factoring in"
        f" broader market trends, potential economic shifts, and diversification strategies."
        f" Here is the trader's decision:\n\n"
        f"{trader_decision}\n\n"
        f"Your task is to challenge both the Aggressive and Conservative Analysts, pointing out"
        f" where each perspective may be overly optimistic or overly cautious. Use insights from"
        f" the following data sources to support a moderate, sustainable strategy to adjust the"
        f" trader's decision:\n\n"
        f"Market Research Report: {market_report}\n"
        f"Social Media Sentiment Report: {sentiment_report}\n"
        f"Latest World Affairs Report: {news_report}\n"
        f"Company Fundamentals Report: {fundamentals_report}\n"
        f"Here is the current conversation history: {history}"
        f" Here is the last response from the aggressive analyst: {last_aggressive}"
        f" Here is the last response from the conservative analyst: {last_conservative}."
        f" If there are no responses from the other viewpoints yet, present your own argument"
        f" based on the available data.\n\n"
        f"Engage actively by analyzing both sides critically, addressing weaknesses in the"
        f" aggressive and conservative arguments to advocate for a more balanced approach."
        f" Challenge each of their points to illustrate why a moderate risk strategy might offer"
        f" the best of both worlds, providing growth potential while safeguarding against extreme"
        f" volatility. Focus on debating rather than simply presenting data, aiming to show that a"
        f" balanced view can lead to the most reliable outcomes."
        f" Output conversationally as if you are speaking without any special formatting.\n\n"
        f"Prefix your response with 'Neutral Analyst: ' then write your argument."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt="You are the Neutral Risk Analyst in a structured risk review.",
        model=cfg.deep_model,
        name="neutral-risk",
    )
    round_n = int(out_path.stem.split("-")[1])
    write_report(out_path, f"Neutral Risk Analyst — Round {round_n}", ticker, trade_date, content)
    return out_path
