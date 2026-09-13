from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client

from things_agent_workflow import server


class StatusGateway:
    @staticmethod
    def list_tags() -> list[dict]:
        return [
            {"title": "waiting"},
            {"title": "deferred"},
            {"title": "solo"},
            {"title": "build"},
        ]

    @staticmethod
    def list_areas() -> list[dict]:
        return [{"uuid": "area-1"}]

    @staticmethod
    def list_projects() -> list[dict]:
        return [{"uuid": "project-1"}]


def test_mcp_lists_semantic_tools_and_calls_read_only_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "gateway", StatusGateway())

    async def exercise() -> None:
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == {
                "capture_handoff",
                "resume_handoff",
                "transition_handoff",
                "review_handoffs",
                "build_workstream_project",
                "workflow_status",
            }
            capture = next(tool for tool in tools if tool.name == "capture_handoff")
            kind_values = capture.input_schema["properties"]["kind"]["enum"]
            assert "task" in kind_values
            assert "decision" in kind_values

            result = await client.call_tool("workflow_status", {})
            assert result.is_error is False
            assert result.data["required_state_tags"] == {
                "waiting": True,
                "deferred": True,
            }

    asyncio.run(exercise())
