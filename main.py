"""Minimal Claude Agent SDK example using the built-in WebFetch tool.

Run with uv (uses the locked project environment):
    export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-..."
    uv run --frozen python main.py
"""

import anyio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from config import Config

PROMPT = (
    "Fetch https://modelcontextprotocol.io and summarize what it is "
    "in 3 short bullet points."
)


async def main() -> None:
    config = Config()
    options = ClaudeAgentOptions(
        # Use the fast/cheap model from config for this lightweight fetch task.
        model=config.quick_model,
        # Auto-approve the WebFetch tool so it runs non-interactively.
        allowed_tools=["WebFetch"],
        permission_mode="acceptEdits",
        max_turns=5,
    )

    async for message in query(prompt=PROMPT, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="")
    print()


if __name__ == "__main__":
    anyio.run(main)
