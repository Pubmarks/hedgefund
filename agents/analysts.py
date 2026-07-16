"""Four specialist analyst agents — Phase 1.

System prompts adapted from TradingAgents.  Data is fetched via flat imports
from the ``tools`` library (see AGENT.md) rather than MCP.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from agent import RATING_INSTRUCTION, run_agent, write_report
from config import Config

_NO_TITLE_INSTRUCTION = (
    "\n\nOutput format: Do NOT include a top-level `#` title or a date/metadata block. "
    "The document title and trade date are added by the system. "
    "Begin your response directly with your first `##` section."
)

# ---------------------------------------------------------------------------
# Shared outer framing (mirrors TradingAgents ChatPromptTemplate outer system)
# ---------------------------------------------------------------------------

_OUTER = (
    "You are a helpful AI assistant, collaborating with other assistants."
    " Use the provided tools to progress towards answering the question."
    " If you are unable to fully answer, that's OK; another assistant with different tools"
    " will help where you left off. Execute what you can to make progress."
    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
)

# ---------------------------------------------------------------------------
# Role-specific system prompts (adapted from TradingAgents source)
# ---------------------------------------------------------------------------

_MARKET_ROLE = (
    "You are a trading assistant tasked with analyzing financial markets. Your role is to select"
    " the **most relevant indicators** for a given market condition or trading strategy from the"
    " following list. The goal is to choose up to **8 indicators** that provide complementary"
    " insights without redundancy. Categories and each category's indicators are:\n\n"
    "Moving Averages:\n"
    "- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and"
    " serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators"
    " for timely signals.\n"
    "- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend"
    " and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend"
    " confirmation rather than frequent trading entries.\n"
    "- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in"
    " momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside"
    " longer averages for filtering false signals.\n\n"
    "MACD Related:\n"
    "- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and"
    " divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility"
    " or sideways markets.\n"
    "- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD"
    " line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.\n"
    "- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize"
    " momentum strength and spot divergence early. Tips: Can be volatile; complement with additional"
    " filters in fast-moving markets.\n\n"
    "Momentum Indicators:\n"
    "- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30"
    " thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may"
    " remain extreme; always cross-check with trend analysis.\n\n"
    "Volatility Indicators:\n"
    "- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a"
    " dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to"
    " effectively spot breakouts or reversals.\n"
    "- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line."
    " Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with"
    " other tools; prices may ride the band in strong trends.\n"
    "- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line."
    " Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false"
    " reversal signals.\n"
    "- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust"
    " position sizes based on current market volatility. Tips: It's a reactive measure, so use it"
    " as part of a broader risk management strategy.\n\n"
    "Volume-Based Indicators:\n"
    "- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price"
    " action with volume data. Tips: Watch for skewed results from volume spikes; use in combination"
    " with other volume analyses.\n\n"
    "You will also receive a VWAP (Volume Weighted Average Price) series computed from daily bars"
    " using typical_price=(H+L+C)/3. Use it to assess whether price is trading above or below the"
    " cumulative VWAP benchmark, identify mean-reversion setups, and gauge institutional price levels.\n\n"
    "- Select indicators that provide diverse and complementary information. Avoid redundancy"
    " (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for"
    " the given market context. Write a very detailed and nuanced report of the trends you observe."
    " Provide specific, actionable insights with supporting evidence to help traders make informed"
    " decisions. Make sure to append a Markdown table at the end of the report to organize key"
    " points in the report, organized and easy to read."
)

_SOCIAL_ROLE = (
    "You are a social media and company specific news researcher/analyst tasked with analyzing"
    " social media posts, recent company news, and public sentiment for a specific company over"
    " the past week. You will be given a company's name your objective is to write a comprehensive"
    " long report detailing your analysis, insights, and implications for traders and investors on"
    " this company's current state after looking at social media and what people are saying about"
    " that company, analyzing sentiment data of what people feel each day about the company, and"
    " looking at recent company news. Try to look at all sources possible from social media to"
    " sentiment to news. Provide specific, actionable insights with supporting evidence to help"
    " traders make informed decisions."
    " Make sure to append a Markdown table at the end of the report to organize key points in the"
    " report, organized and easy to read."
)

_NEWS_ROLE = (
    "You are a news researcher tasked with analyzing recent news and trends over the past week."
    " Please write a comprehensive report of the current state of the world that is relevant for"
    " trading and macroeconomics. Use the available tools for company-specific or targeted news"
    " searches and broader macroeconomic news. Provide specific, actionable insights with"
    " supporting evidence to help traders make informed decisions."
    " Make sure to append a Markdown table at the end of the report to organize key points in the"
    " report, organized and easy to read.\n\n"
    "Your macro analysis must cover ALL of the following categories where data is available:\n\n"
    "WARFARE & GEOPOLITICS: Active conflicts, ceasefires, sanctions, NATO posture, South China Sea,"
    " Taiwan Strait. Assess escalation risk and commodity/supply-chain implications.\n\n"
    "TARIFFS & TRADE: US-China tariff escalations, EU-US trade disputes, Section 232/301 actions,"
    " WTO rulings. Quantify impact on sectors relevant to the instrument under review.\n\n"
    "LABOUR MARKETS: US nonfarm payrolls, unemployment rate, jobless claims. Eurozone HICP"
    " unemployment, German IFO. Assess whether labour market is tightening or loosening.\n\n"
    "CENTRAL BANKS: Fed, ECB, BoE, BoJ most recent decision and forward guidance. Current policy"
    " rate, dot-plot or equivalent projection, next meeting date.\n\n"
    "SOVEREIGN DEBT & FISCAL: US deficit/GDP ratio, Treasury issuance calendar, debt ceiling."
    " Eurozone spreads (BTP-Bund). UK OBR forecasts.\n\n"
    "COMMODITIES & ENERGY: Brent/WTI, TTF natural gas, gold, copper. OPEC+ output decisions,"
    " strategic reserve releases.\n\n"
    "For each category, state the most recent hard number, the direction of travel, and the"
    " implication for risk assets and the specific instrument being analysed."
)

_FUNDAMENTALS_ROLE = (
    "You are a researcher tasked with analyzing fundamental information over the past week about a"
    " company. Please write a comprehensive report of the company's fundamental information such as"
    " financial documents, company profile, basic company financials, and company financial history"
    " to gain a full view of the company's fundamental information to inform traders. Make sure to"
    " include as much detail as possible. Provide specific, actionable insights with supporting"
    " evidence to help traders make informed decisions."
    " Make sure to append a Markdown table at the end of the report to organize key points in the"
    " report, organized and easy to read."
    " Use the available tools: `get_fundamentals` for comprehensive company analysis,"
    " `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial"
    " statements.\n\n"
    "For P/E valuation analysis: use p_e_median_5yr as the primary historical baseline — it is"
    " robust to outlier quarters. If p_e_lossy_5yr > 0, the mean is distorted by loss-making"
    " periods; rely on p_e_median_5yr and p_e_shiller_5yr instead. Always compare the current"
    " P/E against the 5-year median and state explicitly whether the stock is trading cheap,"
    " fair, or stretched relative to its own history."
)


# ---------------------------------------------------------------------------
# Data-fetching helpers — deterministic work, not in agents
# ---------------------------------------------------------------------------

def _extract_content(result: dict, path_hint: str = "") -> str:
    """Extract text content from a tool result's artifacts."""
    for art in result.get("artifacts") or []:
        if path_hint and art.get("path_hint") != path_hint:
            continue
        content = art.get("content", "")
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    return ""


def _extract_all(result: dict) -> dict[str, str]:
    """Extract all artifact contents keyed by path_hint."""
    out: dict[str, str] = {}
    for art in result.get("artifacts") or []:
        content = art.get("content", "")
        out[art["path_hint"]] = (
            content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
        )
    return out


def _instrument_context(ticker: str) -> str:
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`). "
        "Do NOT mention, reference, or analyze any other ticker symbol."
    )


def _ohlcv_start(trade_date: str, years: int) -> str:
    d = date.fromisoformat(trade_date)
    try:
        start = d.replace(year=d.year - years)
    except ValueError:
        start = d.replace(year=d.year - years, day=28)
    return start.isoformat()


def _news_start(trade_date: str, days: int) -> str:
    d = date.fromisoformat(trade_date)
    return (d - timedelta(days=days)).isoformat()


def _read_articles(pages_dir: Path) -> str:
    """Read article bodies from a pages directory with manifest.json."""
    manifest_path = pages_dir / "manifest.json"
    if not manifest_path.exists():
        return ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parts = []
    for entry in manifest.get("articles", []):
        f = pages_dir / entry["file"]
        if f.exists():
            parts.append(f"\n\n--- {entry['headline']} ---\n{f.read_text(encoding='utf-8')}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------

async def run_market_analyst(ticker: str, trade_date: str, cfg: Config) -> Path:
    from tools.indicators import fetch_indicators
    from tools.ohlcv import fetch_ohlcv
    from tools.vwap import fetch_vwap

    out_path = cfg.reports_dir / ticker / "market.md"
    ohlcv_start = _ohlcv_start(trade_date, cfg.ohlcv_years)

    ohlcv_result = fetch_ohlcv(ticker, ohlcv_start, trade_date)
    indicators_result = fetch_indicators(
        symbol=ticker,
        indicators=["close_50_sma", "close_200_sma", "close_10_ema",
                     "rsi", "macd", "macdh", "boll", "atr"],
        curr_date=trade_date,
        lookback=30,
    )
    vwap_result = fetch_vwap(symbol=ticker, start=ohlcv_start, end=trade_date)

    indicators = _extract_content(indicators_result, "indicators.txt")
    vwap = _extract_content(vwap_result, "vwap.csv")

    prompt = (
        f"Current date: {trade_date}. {_instrument_context(ticker)}\n\n"
        f"## Technical Indicators\n{indicators}\n\n"
        f"## VWAP (daily bars, cumulative from {ohlcv_start})\n{vwap}\n\n"
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_MARKET_ROLE}\n\n{_NO_TITLE_INSTRUCTION}",
        model=cfg.quick_model,
        name="market-analyst",
    )
    write_report(out_path, "Market Technical Analysis", ticker, trade_date, content)
    return out_path


async def run_social_analyst(ticker: str, trade_date: str, cfg: Config) -> Path:
    from tools.news import fetch_news

    out_path = cfg.reports_dir / ticker / "sentiment.md"
    news_start = _news_start(trade_date, cfg.news_lookback_days)

    news_result = fetch_news(
        ticker=ticker, start=news_start, end=trade_date, include_pages=True,
    )
    arts = _extract_all(news_result)
    news_company = arts.get("news_company.txt", "")
    pages_dir = cfg.reports_dir / ticker / "data" / "news_company_pages"
    # Write article pages to disk for reading
    for path_hint, content in arts.items():
        if path_hint.startswith("news_company_pages/"):
            dest = cfg.reports_dir / ticker / "data" / path_hint
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
    articles = _read_articles(pages_dir)

    prompt = (
        f"Current date: {trade_date}. {_instrument_context(ticker)}\n\n"
        f"## Company News\n{news_company}\n\n"
        f"## Article Bodies\n{articles}\n\n"
        f"Focus only on company-specific news and sentiment.\n"
        f"You may use WebSearch and WebFetch to supplement with any missing social media sentiment"
        f" or recent developments."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_SOCIAL_ROLE}\n\n{_NO_TITLE_INSTRUCTION}",
        allowed_tools=("WebSearch", "WebFetch"),
        model=cfg.quick_model,
        name="social-analyst",
    )
    write_report(out_path, "Social Sentiment Analysis", ticker, trade_date, content)
    return out_path


async def run_news_analyst(ticker: str, trade_date: str, cfg: Config) -> Path:
    from tools.insider import fetch_insider
    from tools.macro import fetch_macro_data
    from tools.news import fetch_news

    out_path = cfg.reports_dir / ticker / "news.md"
    global_dir = cfg.reports_dir / "global"
    news_start = _news_start(trade_date, cfg.news_lookback_days)

    news_result = fetch_news(
        ticker=ticker, start=news_start, end=trade_date, include_pages=False,
    )
    insider_result = fetch_insider(ticker)

    news_company = _extract_content(news_result, "news_company.txt")
    insider = _extract_content(insider_result, "insider.txt")
    global_summary = read_report(global_dir / "news_global_summary.md")
    macro_data_text = read_report(global_dir / "macro_data.txt")
    macro_web = read_report(global_dir / "macro_web_research.md")

    prompt = (
        f"Current date: {trade_date}. {_instrument_context(ticker)}\n\n"
        f"## Company News\n{news_company}\n\n"
        f"## Insider Transactions\n{insider}\n\n"
        f"## Global Macro Summary\n{global_summary}\n\n"
        f"## Macro Data (FRED)\n{macro_data_text}\n\n"
        f"## Live Macro Research\n{macro_web}\n\n"
        f"The macro context above is complete — do NOT search for macro data again.\n"
        f"You may use WebSearch and WebFetch only for company-specific gaps: recent {ticker} earnings,"
        f" product announcements, regulatory filings, or analyst coverage not covered in the news above."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_NEWS_ROLE}\n\n{_NO_TITLE_INSTRUCTION}",
        allowed_tools=("WebSearch", "WebFetch"),
        model=cfg.quick_model,
        name="news-analyst",
    )
    write_report(out_path, "News & Macro Analysis", ticker, trade_date, content)
    return out_path


async def run_fundamentals_analyst(ticker: str, trade_date: str, cfg: Config) -> Path:
    from tools.avgpe import fetch_avgpe
    from tools.fundamentals import fetch_fundamentals
    from tools.insider import fetch_insider
    from tools.statement import fetch_statement

    out_path = cfg.reports_dir / ticker / "fundamentals.md"

    fundamentals_result = fetch_fundamentals(ticker)
    bs_result = fetch_statement(ticker, "balance_sheet", "quarterly", trade_date)
    cf_result = fetch_statement(ticker, "cashflow", "quarterly", trade_date)
    inc_result = fetch_statement(ticker, "income", "quarterly", trade_date)
    insider_result = fetch_insider(ticker)
    avgpe_result = fetch_avgpe(ticker)

    fundamentals = _extract_content(fundamentals_result, "fundamentals.txt")
    balance_sheet = _extract_content(bs_result, "balance_sheet.csv")
    cashflow = _extract_content(cf_result, "cashflow.csv")
    income = _extract_content(inc_result, "income.csv")
    insider = _extract_content(insider_result, "insider.txt")
    avgpe_arts = _extract_all(avgpe_result)
    avgpe = avgpe_arts.get("avgpe_5.txt", "")
    avgpe_10 = avgpe_arts.get("avgpe_10.txt", "")
    if avgpe_10:
        avgpe = f"{avgpe}\n\n{avgpe_10}" if avgpe else avgpe_10

    prompt = (
        f"Current date: {trade_date}. {_instrument_context(ticker)}\n\n"
        f"## Fundamentals\n{fundamentals}\n\n"
        f"## Balance Sheet\n{balance_sheet}\n\n"
        f"## Cash Flow\n{cashflow}\n\n"
        f"## Income Statement\n{income}\n\n"
        f"## Insider Transactions\n{insider}\n\n"
        f"## Average P/E\n{avgpe}\n\n"
        f"For P/E valuation: compare current P/E against p_e_median_5yr as the primary baseline."
        f" If p_e_lossy_5yr > 0, the mean is unreliable — use median and p_e_shiller_5yr instead."
        f" Explicitly state whether the stock is cheap, fair, or stretched vs its own 5-year history."
        f"{RATING_INSTRUCTION}"
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_FUNDAMENTALS_ROLE}\n\n{_NO_TITLE_INSTRUCTION}",
        model=cfg.quick_model,
        name="fundamentals-analyst",
    )
    write_report(out_path, "Fundamentals Analysis", ticker, trade_date, content)
    return out_path


def _file_is_fresh(path: Path, max_age_hours: float = 12.0) -> bool:
    from datetime import datetime, timezone
    if not path.exists():
        return False
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return age.total_seconds() < max_age_hours * 3600


async def run_global_news_summarizer(trade_date: str, cfg: Config) -> Path:
    """Summarise global news + FRED macro into a single structured file.

    Skips if the summary is already fresh (within 12 hours).
    """
    global_dir = cfg.reports_dir / "global"
    summary_path = global_dir / "news_global_summary.md"
    pages_dir = global_dir / "news_global_pages"

    if _file_is_fresh(summary_path):
        return summary_path

    from tools.global_news import fetch_global_news
    from tools.macro import fetch_macro_data

    gn_result = fetch_global_news(curr_date=trade_date, lookback=cfg.news_lookback_days)
    macro_result = fetch_macro_data(curr_date=trade_date)

    gn_arts = _extract_all(gn_result)
    news_index = ""
    for path_hint, content in gn_arts.items():
        if not path_hint.startswith("news_global_pages/"):
            news_index = content
            dest = global_dir / path_hint
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        else:
            dest = global_dir / path_hint
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
    macro_data_text = _extract_content(macro_result, "macro_data.txt")
    if macro_data_text:
        macro_path = global_dir / "macro_data.txt"
        macro_path.parent.mkdir(parents=True, exist_ok=True)
        macro_path.write_text(macro_data_text, encoding="utf-8")

    articles_text = _read_articles(pages_dir)

    prompt = (
        f"Current date: {trade_date}.\n\n"
        f"## News Index\n{news_index}\n\n"
        f"## Macro Data (FRED)\n{macro_data_text}\n\n"
        f"## Article Bodies\n{articles_text}\n\n"
        f"Produce a structured macro summary using exactly these section headings:\n\n"
        f"## Warfare & Geopolitics\n"
        f"## Tariffs & Trade\n"
        f"## Labour Markets\n"
        f"## Central Banks\n"
        f"## Sovereign Debt & Fiscal\n"
        f"## Commodities & Energy\n"
        f"## China Macro\n\n"
        f"For each section: 3-5 bullet points with the most important developments."
        f" Include hard numbers (%, $, bps) wherever available.\n"
        f"End with a ## Macro Risk Assessment paragraph on dominant tailwinds and headwinds for risk assets."
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_NO_TITLE_INSTRUCTION}",
        model=cfg.quick_model,
        name="global-news-summarizer",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


async def run_macro_web_researcher(trade_date: str, cfg: Config) -> Path:
    """Fetch live macro data points via WebSearch/WebFetch and cache for the day."""
    out_path = cfg.reports_dir / "global" / "macro_web_research.md"
    if _file_is_fresh(out_path):
        return out_path

    prompt = (
        f"Current date: {trade_date}.\n\n"
        f"Search for the latest values for each of the following macro data points.\n"
        f"Use targeted WebSearch and WebFetch queries — prefer Reuters, FT, Bloomberg, WSJ,"
        f" Fed.gov, ECB.europa.eu, BLS.gov as sources.\n\n"
        f"Data points to research:\n"
        f"- US nonfarm payrolls and unemployment rate (most recent release)\n"
        f"- Fed funds rate, most recent FOMC decision, and forward guidance\n"
        f"- ECB deposit rate, most recent decision, and forward guidance\n"
        f"- US-China tariff status and any recent escalations\n"
        f"- Active warfare developments with commodity/supply-chain implications\n"
        f"- Brent crude spot price and latest OPEC+ output decision\n"
        f"- Eurozone unemployment rate and manufacturing PMI\n\n"
        f"For each data point: state the hard number, the date of the reading, and the"
        f" direction of travel (improving / deteriorating / stable)."
    )

    content = await run_agent(
        prompt=prompt,
        system_prompt=f"{_OUTER}\n\n{_NO_TITLE_INSTRUCTION}",
        allowed_tools=("WebSearch", "WebFetch"),
        model=cfg.quick_model,
        name="macro-web-researcher",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


# Re-export read_report for phase modules that import from analysts
from agent import read_report  # noqa: E402, F401
