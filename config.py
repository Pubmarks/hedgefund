from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "out"
DEFAULT_MEMORY_PATH = Path.home() / ".hedgefund" / "memory.md"
DEFAULT_FREE_MODEL = "opencode/big-pickle"


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "WARNING").strip().upper() or "WARNING"
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)


_configure_logging()


@dataclass
class Config:
    # Debate settings
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1

    # Model tiers — OpenCode provider/model format
    quick_model: str = DEFAULT_FREE_MODEL
    deep_model: str = DEFAULT_FREE_MODEL
    epic_model: str = DEFAULT_FREE_MODEL

    # Paths
    reports_dir: Path = field(default_factory=lambda: REPORTS_DIR)
    memory_log_path: Path = field(default_factory=lambda: DEFAULT_MEMORY_PATH)
    memory_log_max_entries: int | None = None

    # OpenCode runtime
    opencode_server_url: str = ""
    opencode_api_key: str = ""

    # OHLCV lookback window in years (used by market analyst)
    ohlcv_years: int = 5

    # News lookback in days (used by social/news analysts)
    news_lookback_days: int = 7


def default_config() -> Config:
    return Config(
        opencode_server_url=os.getenv("OPENCODE_SERVER_URL", ""),
        opencode_api_key=os.getenv("OPENCODE_API_KEY", ""),
        quick_model=os.getenv("HEDGEFUND_QUICK_MODEL", DEFAULT_FREE_MODEL),
        deep_model=os.getenv("HEDGEFUND_DEEP_MODEL", DEFAULT_FREE_MODEL),
        epic_model=os.getenv("HEDGEFUND_EPIC_MODEL", DEFAULT_FREE_MODEL),
    )
