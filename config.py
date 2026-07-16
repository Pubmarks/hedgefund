from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
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
    # Harmless shutdown noise when the SDK tears down its in-process MCP bridge.
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)


_configure_logging()


@dataclass
class Config:
    # Model tiers — OpenCode provider/model format (default: free Zen model)
    quick_model: str = DEFAULT_FREE_MODEL
    deep_model: str = DEFAULT_FREE_MODEL
    epic_model: str = DEFAULT_FREE_MODEL

    # OpenCode runtime — leave server_url empty for subprocess ACP (recommended)
    opencode_server_url: str = ""
    opencode_api_key: str = ""


def default_config() -> Config:
    return Config(
        opencode_server_url=os.getenv("OPENCODE_SERVER_URL", ""),
        opencode_api_key=os.getenv("OPENCODE_API_KEY", ""),
        quick_model=os.getenv("HEDGEFUND_QUICK_MODEL", DEFAULT_FREE_MODEL),
        deep_model=os.getenv("HEDGEFUND_DEEP_MODEL", DEFAULT_FREE_MODEL),
        epic_model=os.getenv("HEDGEFUND_EPIC_MODEL", DEFAULT_FREE_MODEL),
    )
