from dataclasses import dataclass

@dataclass
class Config:
    quick_model: str = "claude-haiku-4-5-20251001"
    deep_model: str = "claude-sonnet-4-6"
    epic_model: str = "claude-opus-4-8"
