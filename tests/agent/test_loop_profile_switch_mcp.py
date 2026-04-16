from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import Config, MCPServerConfig, SwitchProfileConfig
from nanobot.providers.base import GenerationSettings, LLMResponse


class _FakeMCPTool(Tool):
    @property
    def name(self) -> str:
        return "mcp_notionApi_API-post-search"

    @property
    def description(self) -> str:
        return "Fake notion search tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "ok"


def _make_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.generation = GenerationSettings(max_tokens=256)
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="ok", tool_calls=[]))
    provider.chat_stream_with_retry = AsyncMock(return_value=LLMResponse(content="ok", tool_calls=[]))
    return provider


def _make_config(
    workspace: Path,
    *,
    switch_profiles: dict[str, SwitchProfileConfig] | None = None,
) -> Config:
    config = Config()
    config.agents.defaults.workspace = str(workspace)
    config.agents.defaults.model = "test-model"
    config.agents.defaults.switch_profiles = switch_profiles or {}
    config.tools.mcp_servers = {
        "notionApi": MCPServerConfig(command="fake-mcp", enabled_tools=["*"]),
    }
    return config


def _tool_names(definitions: list[dict]) -> list[str]:
    names: list[str] = []
    for definition in definitions:
        function = definition.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.append(function["name"])
    return names


@pytest.mark.asyncio
async def test_switch_profile_reconnects_mcp_before_next_message(tmp_path: Path, monkeypatch) -> None:
    base_workspace = tmp_path / "base-workspace"
    rem_workspace = tmp_path / "rem-workspace"
    base_workspace.mkdir()
    rem_workspace.mkdir()
    rem_config_path = tmp_path / "rem-config.json"
    rem_config_path.write_text("{}", encoding="utf-8")

    switch_profiles = {
        "Rem": SwitchProfileConfig(
            config=str(rem_config_path),
            workspace=str(rem_workspace),
            description="Research profile",
        ),
    }
    base_config = _make_config(base_workspace, switch_profiles=switch_profiles)
    rem_config = _make_config(rem_workspace, switch_profiles=switch_profiles)
    provider = _make_provider()
    connect_calls: list[tuple[str, ...]] = []

    async def fake_connect_mcp_servers(mcp_servers, registry, stack) -> None:
        connect_calls.append(tuple(sorted(mcp_servers)))
        registry.register(_FakeMCPTool())

    monkeypatch.setattr("nanobot.agent.tools.mcp.connect_mcp_servers", fake_connect_mcp_servers)
    monkeypatch.setattr(
        "nanobot.config.loader.load_config",
        lambda path=None: rem_config if Path(path).resolve() == rem_config_path.resolve() else base_config,
    )
    monkeypatch.setattr("nanobot.config.loader.resolve_config_env_vars", lambda config: config)
    monkeypatch.setattr("nanobot.nanobot._make_provider", lambda _config: provider)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=base_config.workspace_path,
        model=base_config.agents.defaults.model,
        mcp_servers=base_config.tools.mcp_servers,
        switch_profiles=base_config.agents.defaults.switch_profiles,
    )

    await loop._connect_mcp()
    assert "mcp_notionApi_API-post-search" in loop.tools.tool_names

    ok, _ = await loop.switch_profile("Rem")

    assert ok is True
    assert loop.active_profile_name == "Rem"
    assert len(connect_calls) == 2
    assert "mcp_notionApi_API-post-search" in loop.tools.tool_names

    provider.chat_with_retry.reset_mock()
    await loop.process_direct(
        "search notion page",
        session_key="weixin:test-chat",
        channel="weixin",
        chat_id="test-chat",
    )

    sent_tools = provider.chat_with_retry.await_args.kwargs["tools"]
    assert "mcp_notionApi_API-post-search" in _tool_names(sent_tools)


@pytest.mark.asyncio
async def test_system_messages_reconnect_mcp_before_llm_request(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = _make_provider()
    connect_calls: list[str] = []

    async def fake_connect_mcp_servers(_mcp_servers, registry, _stack) -> None:
        connect_calls.append("connected")
        registry.register(_FakeMCPTool())

    monkeypatch.setattr("nanobot.agent.tools.mcp.connect_mcp_servers", fake_connect_mcp_servers)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model="test-model",
        mcp_servers={"notionApi": MCPServerConfig(command="fake-mcp", enabled_tools=["*"])},
    )

    loop.tools = ToolRegistry()
    loop._register_default_tools()
    loop._mcp_connected = False
    loop._mcp_stack = None
    provider.chat_with_retry.reset_mock()

    await loop._process_message(
        InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id="weixin:test-chat",
            content="continue",
        )
    )

    assert connect_calls == ["connected"]
    sent_tools = provider.chat_with_retry.await_args.kwargs["tools"]
    assert "mcp_notionApi_API-post-search" in _tool_names(sent_tools)
