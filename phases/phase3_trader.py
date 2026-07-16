"""Phase 3: single Trader agent."""
from __future__ import annotations

from pathlib import Path

from agents.trader import run_trader
from config import Config


async def run_phase3(
    ticker: str,
    trade_date: str,
    debate_path: Path,
    cfg: Config,
) -> Path:
    """Convert debate synthesis into a concrete trader proposal. Returns path."""
    debate = debate_path.read_text(encoding="utf-8")
    out_path = cfg.reports_dir / ticker / "investment_plan.md"
    if not out_path.exists():
        await run_trader(
            ticker=ticker,
            trade_date=trade_date,
            out_path=out_path,
            investment_plan=debate,
            cfg=cfg,
        )
    return out_path
