"""Shared helper for running OpenCode agent sessions."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import anyio
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

logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)

REASONING_AGENT = "hedgefund-reasoning"
WEB_AGENT = "hedgefund-web"

_CLAUDE_TO_OPENCODE = {"WebSearch": "websearch", "WebFetch": "webfetch"}

# Cap concurrent sessions to avoid saturating the rate limit window when
# Phase 1 (4 analysts) or Phase 4 (3 risk analysts) fan out in parallel.
_CONCURRENCY = 4
_SEM: asyncio.Semaphore | None = None

# Heartbeat while an agent is waiting on OpenCode (connect / prompt / tools).
_STUCK_HEARTBEAT_S = float(os.getenv("HEDGEFUND_STUCK_HEARTBEAT_S", "30"))

# Auth files to copy into each isolated OpenCode data dir (env keys still win).
_OPENCODE_AUTH_FILES = ("auth.json",)


def _semaphore() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(_CONCURRENCY)
    return _SEM


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


# ---------------------------------------------------------------------------
# Policy injection
# ---------------------------------------------------------------------------

_POLICY_PATH = REPO_ROOT / "POLICY.md"
_policy_cache: str | None = None
_policy_loaded = False


def _policy() -> str:
    global _policy_cache, _policy_loaded
    if not _policy_loaded:
        _policy_loaded = True
        if _POLICY_PATH.exists():
            _policy_cache = _POLICY_PATH.read_text(encoding="utf-8")
    return _policy_cache or ""


def _build_system(system_prompt: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    policy = _policy()
    parts = [f"Current date and time: {now}", system_prompt, policy]
    return "\n\n---\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Progress logging
# ---------------------------------------------------------------------------

def _fmt_input(tool_name: str, inp: dict) -> str:
    if tool_name in ("websearch", "WebSearch"):
        return str(inp.get("query", inp))[:100]
    if tool_name in ("webfetch", "WebFetch"):
        return str(inp.get("url", inp))[:100]
    if tool_name in ("bash", "Bash"):
        cmd = inp.get("command", "").strip().replace("\n", " ")
        return cmd[:100]
    if tool_name in ("write", "read", "edit", "Write", "Read", "Edit", "MultiEdit"):
        return inp.get("file_path", inp.get("path", ""))
    if tool_name in ("glob", "Glob"):
        return inp.get("pattern", "")
    if tool_name in ("grep", "Grep"):
        return f"{inp.get('pattern', '')}  {inp.get('path', '')}"
    return str(inp)[:100]


def _log(name: str, tag: str, detail: str = "") -> None:
    label = f"[{name}]"
    parts = [label, tag]
    if detail:
        parts.append(detail)
    print("  ".join(parts), flush=True)


class _AgentProgress:
    """Track stage + last activity so long hangs print a stuck-state heartbeat."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.stage = "init"
        self.detail = ""
        self.started = time.monotonic()
        self.last_activity = self.started
        self._task: asyncio.Task[None] | None = None

    def set(self, stage: str, detail: str = "") -> None:
        self.stage = stage
        self.detail = detail
        self.last_activity = time.monotonic()
        if detail:
            _log(self.name, stage, detail)
        else:
            _log(self.name, stage)

    def touch(self, detail: str = "") -> None:
        self.last_activity = time.monotonic()
        if detail:
            self.detail = detail

    def start_heartbeat(self) -> None:
        if _STUCK_HEARTBEAT_S <= 0:
            return
        self._task = asyncio.create_task(self._heartbeat())

    async def _heartbeat(self) -> None:
        try:
            while True:
                await asyncio.sleep(_STUCK_HEARTBEAT_S)
                now = time.monotonic()
                idle = now - self.last_activity
                elapsed = now - self.started
                if idle < _STUCK_HEARTBEAT_S:
                    continue
                detail = (
                    f"stage={self.stage}  idle={idle:.0f}s  elapsed={elapsed:.0f}s"
                )
                if self.detail:
                    detail = f"{detail}  last={self.detail}"
                _log(self.name, "stuck?", detail)
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


def _patch_acp_session(client: SDKClient, progress: _AgentProgress) -> None:
    """Fix ACP permission method name + surface pending tool/permission state.

    OpenCode sends ``session/request_permission`` (ACP v1). opencode-agent-sdk
    0.4.x only handles the legacy method ``requestPermission``, so web-tool
    sessions wait forever for a reply that never comes.
    """
    session = client._session  # noqa: SLF001 — subprocess ACP only
    if session is None:
        return

    original_handle = session._handle_message  # noqa: SLF001

    async def _handle_message(msg: dict[str, Any]) -> None:
        method = msg.get("method", "")

        # Normalize ACP v1 permission requests to the SDK's legacy handler.
        if method == "session/request_permission" and "id" in msg:
            params = msg.get("params") or {}
            tool_call = params.get("toolCall") or {}
            tool_name = tool_call.get("title") or tool_call.get("kind") or "tool"
            tool_input = tool_call.get("rawInput") or {}
            detail = _fmt_input(str(tool_name), tool_input if isinstance(tool_input, dict) else {})
            progress.set("permission", f"{tool_name}  {detail}".strip())
            await session._handle_permission_request(  # noqa: SLF001
                {**msg, "method": "requestPermission"}
            )
            progress.touch("permission-granted")
            return

        if method in ("session/update", "sessionUpdate"):
            params = msg.get("params") or {}
            update = params.get("update", params)
            utype = update.get("sessionUpdate", "")
            if utype == "tool_call":
                tool_name = update.get("title") or "tool"
                status = update.get("status") or "pending"
                tool_input = update.get("rawInput") or {}
                detail = _fmt_input(str(tool_name), tool_input if isinstance(tool_input, dict) else {})
                progress.set(f"tool:{status}", f"{tool_name}  {detail}".strip())
            elif utype == "tool_call_update":
                tool_call_id = update.get("toolCallId", "")
                status = update.get("status") or "update"
                tc = session._tool_calls.get(tool_call_id, {})  # noqa: SLF001
                tool_name = tc.get("name") or update.get("title") or tool_call_id or "tool"
                progress.touch(f"tool:{status}:{tool_name}")
                if status in ("in_progress", "pending"):
                    tool_input = update.get("rawInput") or tc.get("input") or {}
                    detail = _fmt_input(str(tool_name), tool_input if isinstance(tool_input, dict) else {})
                    progress.set(f"tool:{status}", f"{tool_name}  {detail}".strip())
            elif utype in ("agent_message_chunk", "agent_thought_chunk"):
                progress.touch(utype)
            elif utype:
                progress.touch(utype)

        await original_handle(msg)

    session._handle_message = _handle_message  # noqa: SLF001


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def instrument_context(ticker: str) -> str:
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`). "
        "Do NOT mention, reference, or analyze any other ticker symbol."
    )


def read_report(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_report(path: Path, title: str, ticker: str, trade_date: str, content: str) -> None:
    content = _strip_leading_title(content)
    header = f"# {title} — {ticker}\n*Trade date: {trade_date}*\n\n---\n\n"
    path.write_text(header + content, encoding="utf-8")


def _strip_leading_title(content: str) -> str:
    """Drop an agent-emitted leading H1 and any immediate chrome lines."""
    lines = content.lstrip().splitlines()
    if not lines or not lines[0].startswith("# "):
        return content.lstrip()
    del lines[0]
    while lines:
        stripped = lines[0].strip()
        if not stripped:
            lines.pop(0)
            continue
        if stripped in ("---", "***"):
            lines.pop(0)
            continue
        if lines[0].lstrip().startswith(("*", "_", "**")):
            lines.pop(0)
            continue
        break
    return "\n".join(lines).lstrip()


# ---------------------------------------------------------------------------
# Rating constants
# ---------------------------------------------------------------------------

RATING_SCALE = (
    "**Rating Scale** (use exactly one):\n"
    "- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position\n"
    "- **Overweight**: Constructive view; recommend gradually increasing exposure\n"
    "- **Hold**: Balanced view; recommend maintaining the current position\n"
    "- **Underweight**: Cautious view; recommend trimming exposure\n"
    "- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position\n\n"
    "Commit to a clear stance; reserve Hold only when evidence on both sides is genuinely balanced."
)

RATING_INSTRUCTION = (
    f"\n\nInclude a `## Rating` section. State exactly one rating from the scale below"
    f" and one sentence justifying your choice.\n\n{RATING_SCALE}"
)


# ---------------------------------------------------------------------------
# OpenCode readiness
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# OpenCode execution paths
# ---------------------------------------------------------------------------

async def _set_session_mode(client: SDKClient, mode_id: str) -> bool:
    """Set the session mode. Returns True on success, False on failure."""
    session = client._session  # noqa: SLF001 — subprocess ACP only
    if session is None:
        return False
    try:
        await session._send_request(  # noqa: SLF001
            "session/set_mode",
            {"sessionId": session.session_id, "modeId": mode_id},
        )
        return True
    except Exception as exc:
        _log("", "mode-fallback", f"Failed to set mode {mode_id}: {exc}; using default")
        return False


def _isolated_opencode_env() -> tuple[dict[str, str], Path]:
    """Per-session XDG dirs so concurrent ``opencode acp`` processes do not share a DB.

    Two ACP subprocesses with the same ``XDG_DATA_HOME`` deadlock on OpenCode's
    SQLite DB: one connects, the other hangs forever inside ``connect()``.
    """
    root = Path(tempfile.mkdtemp(prefix="hedgefund-opencode-"))
    data = root / "share"
    state = root / "state"
    cache = root / "cache"
    for path in (data, state, cache):
        path.mkdir(parents=True, exist_ok=True)

    # Preserve credentials from the real data dir when present.
    real_data = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    ) / "opencode"
    dest = data / "opencode"
    dest.mkdir(parents=True, exist_ok=True)
    if real_data.is_dir():
        for name in _OPENCODE_AUTH_FILES:
            src = real_data / name
            if src.is_file():
                shutil.copy2(src, dest / name)

    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(data)
    env["XDG_STATE_HOME"] = str(state)
    env["XDG_CACHE_HOME"] = str(cache)
    return env, root


async def _connect_subprocess(
    client: SDKClient,
    progress: _AgentProgress,
    env: dict[str, str],
) -> None:
    """Connect like SDKClient._connect_subprocess, with isolated env + stage logs."""
    from opencode_agent_sdk._internal.acp import ACPSession
    from opencode_agent_sdk._internal.transport import SubprocessTransport, _find_opencode_binary
    from opencode_agent_sdk.client import _build_mcp_servers

    options = client._options  # noqa: SLF001
    transport = SubprocessTransport(cwd=options.cwd)

    progress.set("connecting", "spawn opencode acp")
    binary = _find_opencode_binary()
    transport._process = await anyio.open_process(  # noqa: SLF001
        [binary, "acp", "--print-logs", "--log-level", "INFO", "--cwd", transport._cwd],  # noqa: SLF001
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    transport._stderr_scope = await anyio.create_task_group().__aenter__()  # noqa: SLF001
    transport._stderr_scope.start_soon(transport._drain_stderr)  # noqa: SLF001
    client._transport = transport  # noqa: SLF001

    session = ACPSession(transport=transport, hooks=options.hooks)
    client._session = session  # noqa: SLF001
    await session.start_reader()

    progress.set("connecting", "acp initialize")
    await session.initialize()

    effective_servers = dict(options.mcp_servers)
    acp_mcp_servers = _build_mcp_servers(effective_servers)

    progress.set("connecting", "acp session/new")
    if options.resume:
        await session.load_session(
            session_id=options.resume,
            cwd=options.cwd,
            mcp_servers=acp_mcp_servers,
        )
    else:
        await session.new_session(
            cwd=options.cwd,
            mcp_servers=acp_mcp_servers,
            model=options.model or None,
            provider_id=options.provider_id or None,
            permission_mode=options.permission_mode,
            system_prompt=options.system_prompt,
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
    allowed_tools: Sequence[str] = (),
) -> str:
    progress = _AgentProgress(name)
    progress.start_heartbeat()
    options = AgentOptions(
        cwd=str(REPO_ROOT),
        model=model_id,
        provider_id=provider_id,
        system_prompt=full_system,
        max_turns=max_turns,
        allowed_tools=_opencode_tools(allowed_tools) if allowed_tools else [],
    )
    client = SDKClient(options=options)
    env, isolated_root = _isolated_opencode_env()
    try:
        await _connect_subprocess(client, progress, env)
        _patch_acp_session(client, progress)
        progress.set("connected", f"session={getattr(client._session, 'session_id', '')}")  # noqa: SLF001

        progress.set("set-mode", mode_id)
        mode_ok = await _set_session_mode(client, mode_id)
        if not mode_ok:
            progress.set("warn", f"mode '{mode_id}' unavailable; proceeding with default agent")

        progress.set("querying", f"prompt_chars={len(prompt)}")
        await client.query(prompt)
        progress.set("receiving", "waiting for OpenCode stream")

        last_text = ""
        async for message in client.receive_response():
            progress.touch("stream-message")
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        detail = _fmt_input(block.name, block.input)
                        progress.set(f"tool:done:{block.name}", detail)
                    elif isinstance(block, TextBlock):
                        last_text = block.text
                        progress.touch(f"text_chars={len(block.text)}")
            elif isinstance(message, SystemMessage) and message.subtype == "tool_error":
                detail = str(message.data.get("error", message.data))[:120]
                progress.set("tool-error", detail)
            elif isinstance(message, ResultMessage):
                duration = f"{message.duration_ms / 1000:.1f}s" if message.duration_ms else ""
                cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else ""
                turns = f"turns={message.num_turns}"
                summary = "  ".join(x for x in [duration, cost, turns] if x)
                progress.set("done", summary)
        return last_text
    finally:
        await progress.stop()
        await client.disconnect()
        shutil.rmtree(isolated_root, ignore_errors=True)


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
        allowed_tools=allowed_tools,
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

    sem = _semaphore()
    if sem.locked():
        _log(name, "waiting", f"concurrency={_CONCURRENCY} (slot busy)")
    async with sem:
        _log(name, "running")
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


__all__ = [
    "ensure_opencode_ready",
    "run_agent",
    "REASONING_AGENT",
    "WEB_AGENT",
    "RATING_SCALE",
    "RATING_INSTRUCTION",
    "instrument_context",
    "read_report",
    "write_report",
]
