from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "out"
DEFAULT_MEMORY_PATH = Path.home() / ".hedgefund" / "memory.md"
DEFAULT_FREE_MODEL = "opencode/big-pickle"

# OpenCode UI.error always wraps with ANSI: "\x1b[91m\x1b[1mError: \x1b[0m…"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class _DropOpencodeNoise(logging.Filter):
    """Hide OpenCode CLI catch-all stderr that the SDK re-logs as WARNING.

    OpenCode's top-level catch prints ``Error: Unexpected error`` via UI.error,
    which embeds ANSI codes, so matching must strip escapes first.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith("opencode_agent_sdk"):
            return True
        msg = _ANSI_RE.sub("", record.getMessage())
        if "opencode stderr:" in msg and "Unexpected error" in msg:
            return False
        if msg.strip() in {"Unexpected error", "Error: Unexpected error"}:
            return False
        return True


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
    noise = _DropOpencodeNoise()
    transport = logging.getLogger("opencode_agent_sdk._internal.transport")
    transport.addFilter(noise)
    logging.getLogger("opencode_agent_sdk").addFilter(noise)
    for handler in logging.root.handlers:
        handler.addFilter(noise)


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

    # OHLCV lookback window in years (used by market analyst)
    ohlcv_years: int = 5

    # News lookback in days (used by social/news analysts)
    news_lookback_days: int = 7


def default_config() -> Config:
    return Config(
        quick_model=os.getenv("HEDGEFUND_QUICK_MODEL", DEFAULT_FREE_MODEL),
        deep_model=os.getenv("HEDGEFUND_DEEP_MODEL", DEFAULT_FREE_MODEL),
        epic_model=os.getenv("HEDGEFUND_EPIC_MODEL", DEFAULT_FREE_MODEL),
    )
