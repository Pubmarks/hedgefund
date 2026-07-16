"""Deferred reflection via OpenCode."""
from __future__ import annotations

from agent import run_agent

_REFLECTION_SYSTEM = (
    "You are a trading analyst reviewing your own past decision now that the outcome is known.\n"
    "Write exactly 2-4 sentences of plain prose (no bullets, no headers, no markdown).\n\n"
    "Cover in order:\n"
    "1. Was the directional call correct? (cite the alpha figure)\n"
    "2. Which part of the investment thesis held or failed?\n"
    "3. One concrete lesson to apply to the next similar analysis.\n\n"
    "Be specific and terse. Your output will be stored verbatim in a decision log "
    "and re-read by future analysts, so every word must earn its place."
)


async def reflect(
    final_decision: str,
    raw_return: float,
    alpha_return: float,
) -> str:
    """Generate a 2-4 sentence reflection on a completed trade."""
    prompt = (
        f"Raw return: {raw_return:+.1%}\n"
        f"Alpha vs SPY: {alpha_return:+.1%}\n\n"
        f"Final Decision:\n{final_decision}"
    )
    result = await run_agent(
        prompt=prompt,
        system_prompt=_REFLECTION_SYSTEM,
        allowed_tools=[],
        max_turns=1,
        name="reflection",
    )
    return result.strip()
