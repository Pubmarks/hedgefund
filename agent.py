"""Shared helper for running OpenCode agent sessions."""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any, Sequence

from opencode_agent_sdk import (
    AgentOptions,
    AssistantMessage,
    ResultMessage,
    SDKClient,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
)

from config import DEFAULT_FREE_MODEL, REPO_ROOT

REASONING_AGENT = "hedgefund-reasoning"
WEB_AGENT = "hedgefund-web"

_CLAUDE_TO_OPENCODE = {"WebSearch": "websearch", "WebFetch": "webfetch"}


def _runtime() -> dict[str, str]:
    return {
        "server_url": os.getenv("OPENCODE_SERVER_URL", "").rstrip("/"),
        "api_key": os.getenv("OPENCODE_API_KEY", ""),
    }


def _parse_model(model: str | None) -> tuple[str, str]:
    value = model or DEFAULT_FREE_MODEL
    if "/" in value:
        provider, model_id = value.split("/", 1)
        return provider, model_id
    return "opencode", value


def _opencode_tools(allowed: Sequence[str]) -> list[str]:
    return [_CLAUDE_TO_OPENCODE.get(t, t.lower()) for t in allowed]


def _build_system(system_prompt: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [f"Current date and time: {now}", system_prompt]
    return "\n\n---\n\n".join(p for p in parts if p)


def _fmt_input(tool_name: str, inp: dict) -> str:
    if tool_name in ("websearch", "WebSearch"):
        return str(inp.get("query", inp))[:100]
    if tool_name in ("webfetch", "WebFetch"):
        return str(inp.get("url", inp))[:100]
    return str(inp)[:100]


def _log(name: str, tag: str, detail: str = "") -> None:
    parts = [f"[{name}]", tag]
    if detail:
        parts.append(detail)
    # Keep stdout clean for the short status line from main.py.
    print("  ".join(parts), flush=True, file=sys.stderr)


async def ensure_opencode_ready(*, server_url: str = "") -> None:
    """Verify OpenCode is reachable before starting work."""
    url = server_url or os.getenv("OPENCODE_SERVER_URL", "").rstrip("/")
    if url:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{url}/global/health")
            resp.raise_for_status()
        return

    if not shutil.which("opencode"):
        raise RuntimeError(
            "OpenCode CLI not found on PATH. Install with:\n"
            "  curl -fsSL https://opencode.ai/install | bash\n"
            "Subprocess mode (default) requires the `opencode` binary."
        )


async def _set_session_mode(client: SDKClient, mode_id: str) -> None:
    session = client._session  # noqa: SLF001 — subprocess ACP only
    if session is None:
        return
    await session._send_request(  # noqa: SLF001
        "session/set_mode",
        {"sessionId": session.session_id, "modeId": mode_id},
    )


def _extract_http_text(messages: Any) -> str:
    last_text = ""
    for item in messages:
        role = getattr(getattr(item, "info", None), "role", None)
        if role != "assistant":
            continue
        for part in item.parts:
            if getattr(part, "type", None) == "text":
                last_text = part.text or last_text
    return last_text


async def _run_http_direct(
    *,
    prompt: str,
    full_system: str,
    provider_id: str,
    model_id: str,
    mode_id: str,
    name: str,
) -> str:
    from opencode_ai import AsyncOpencode

    runtime = _runtime()
    client_kwargs: dict[str, Any] = {"base_url": runtime["server_url"]}
    if runtime["api_key"]:
        client_kwargs["api_key"] = runtime["api_key"]

    client = AsyncOpencode(**client_kwargs)
    try:
        session = await client.session.create()
        try:
            meta = await client.session.chat(
                session.id,
                model_id=model_id,
                provider_id=provider_id,
                mode=mode_id,
                system=full_system,
                parts=[{"type": "text", "text": prompt}],
            )
            messages = await client.session.messages(session.id)
            last_text = _extract_http_text(messages)
            duration = ""
            if meta.time and meta.time.completed is not None and meta.time.created is not None:
                duration = f"{meta.time.completed - meta.time.created:.1f}s"
            cost = f"${meta.cost:.4f}" if meta.cost else ""
            summary = "  ".join(x for x in [duration, cost] if x)
            _log(name, "done", summary)
            return last_text
        finally:
            await client.session.delete(session.id)
    finally:
        await client.close()


async def _run_subprocess_sdk(
    *,
    prompt: str,
    full_system: str,
    provider_id: str,
    model_id: str,
    mode_id: str,
    name: str,
    max_turns: int,
) -> str:
    options = AgentOptions(
        cwd=str(REPO_ROOT),
        model=model_id,
        provider_id=provider_id,
        system_prompt=full_system,
        max_turns=max_turns,
    )
    client = SDKClient(options=options)
    await client.connect()
    try:
        await _set_session_mode(client, mode_id)
        await client.query(prompt)
        last_text = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        detail = _fmt_input(block.name, block.input)
                        _log(name, f"tool:{block.name}", detail)
                    elif isinstance(block, TextBlock):
                        last_text = block.text
            elif isinstance(message, SystemMessage) and message.subtype == "tool_error":
                detail = str(message.data.get("error", message.data))[:120]
                _log(name, "tool-error", detail)
            elif isinstance(message, ResultMessage):
                duration = f"{message.duration_ms / 1000:.1f}s" if message.duration_ms else ""
                cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else ""
                turns = f"turns={message.num_turns}"
                summary = "  ".join(x for x in [duration, cost, turns] if x)
                _log(name, "done", summary)
        return last_text
    finally:
        await client.disconnect()


async def run_llm_direct(
    *,
    prompt: str,
    system_prompt: str,
    model: str | None,
    name: str,
) -> str:
    full_system = _build_system(system_prompt)
    provider_id, model_id = _parse_model(model)
    runtime = _runtime()
    if runtime["server_url"]:
        return await _run_http_direct(
            prompt=prompt,
            full_system=full_system,
            provider_id=provider_id,
            model_id=model_id,
            mode_id=REASONING_AGENT,
            name=name,
        )
    return await _run_subprocess_sdk(
        prompt=prompt,
        full_system=full_system,
        provider_id=provider_id,
        model_id=model_id,
        mode_id=REASONING_AGENT,
        name=name,
        max_turns=1,
    )


async def run_agent_sdk(
    *,
    prompt: str,
    system_prompt: str,
    allowed_tools: Sequence[str],
    max_turns: int,
    model: str | None,
    name: str,
) -> str:
    _ = _opencode_tools(allowed_tools)  # call sites keep Claude names; profile enforces tools
    full_system = _build_system(system_prompt)
    provider_id, model_id = _parse_model(model)
    return await _run_subprocess_sdk(
        prompt=prompt,
        full_system=full_system,
        provider_id=provider_id,
        model_id=model_id,
        mode_id=WEB_AGENT,
        name=name,
        max_turns=max_turns,
    )


async def run_agent(
    *,
    prompt: str,
    system_prompt: str,
    allowed_tools: Sequence[str] = (),
    max_turns: int = 40,
    model: str | None = None,
    name: str = "agent",
) -> str:
    """Run a single OpenCode session and return the final text result."""
    provider_id, model_id = _parse_model(model)
    mode = WEB_AGENT if allowed_tools else REASONING_AGENT
    _log(name, "start", f"model={provider_id}/{model_id} agent={mode}")

    if allowed_tools:
        return await run_agent_sdk(
            prompt=prompt,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            model=model,
            name=name,
        )
    return await run_llm_direct(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        name=name,
    )


# Re-export for callers that want an explicit event loop helper.
__all__ = [
    "ensure_opencode_ready",
    "run_agent",
    "REASONING_AGENT",
    "WEB_AGENT",
]
