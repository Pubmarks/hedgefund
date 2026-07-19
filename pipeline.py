"""Top-level pipeline: runs all four phases for a single ticker."""
from __future__ import annotations

from pathlib import Path

from config import Config, default_config
from memory.log import MemoryLog, parse_rating
from phases.phase1_reports import run_phase1
from phases.phase2_debate import run_phase2
from phases.phase3_trader import run_phase3
from phases.phase4_risk import run_phase4


def _combine_reports(ticker: str, cfg: Config) -> None:
    """Stitch individual agent reports into a single final-report.md."""
    d = cfg.reports_dir / ticker
    files: list[Path] = []

    # Phase 1 analyst reports
    for name in ["market.md", "sentiment.md", "news.md", "fundamentals.md"]:
        if (d / name).exists():
            files.append(d / name)

    # Phase 2 debate rounds
    for round_n in range(1, cfg.max_debate_rounds + 1):
        for side in ("bull", "bear"):
            p = d / "debate" / f"round-{round_n:02d}-{side}.md"
            if p.exists():
                files.append(p)

    # Phase 2 research manager synthesis
    for name in ["debate.md", "investment_plan.md"]:
        if (d / name).exists():
            files.append(d / name)

    # Phase 4 risk discussion rounds
    for round_n in range(1, cfg.max_risk_discuss_rounds + 1):
        for side in ("aggressive", "neutral", "conservative"):
            p = d / "risk" / f"round-{round_n:02d}-{side}.md"
            if p.exists():
                files.append(p)

    # Phase 4 final decision
    if (d / "final_trade_decision.md").exists():
        files.append(d / "final_trade_decision.md")

    md_text = "\n\n---\n\n".join(p.read_text(encoding="utf-8") for p in files)
    out = d / "final-report.md"
    out.write_text(md_text, encoding="utf-8")


async def research(ticker: str, trade_date: str, cfg: Config | None = None) -> str:
    """Full pipeline for one ticker. Returns the final rating string."""
    if cfg is None:
        cfg = default_config()

    from agent import ensure_opencode_ready

    await ensure_opencode_ready()

    memory = MemoryLog(cfg.memory_log_path, cfg.memory_log_max_entries)
    past_context = memory.get_past_context(ticker)

    # Phase 1: parallel analyst fan-out
    report_paths = await run_phase1(ticker, trade_date, cfg)

    # Phase 2: bull/bear debate -> research manager synthesis
    debate_path = await run_phase2(ticker, trade_date, report_paths, cfg)

    # Phase 3: trader decision
    trader_plan_path = await run_phase3(ticker, trade_date, debate_path, cfg)

    # Phase 4: parallel risk positions -> portfolio manager final decision
    final_decision_path = await run_phase4(
        ticker=ticker,
        trade_date=trade_date,
        report_paths=report_paths,
        trader_plan_path=trader_plan_path,
        investment_plan_path=debate_path,
        past_context=past_context,
        cfg=cfg,
    )

    final_decision = final_decision_path.read_text(encoding="utf-8")

    # Store pending decision for deferred reflection
    memory.store_decision(ticker, trade_date, final_decision)

    # Stitch all individual reports into final-report.md
    _combine_reports(ticker, cfg)

    return parse_rating(final_decision)
