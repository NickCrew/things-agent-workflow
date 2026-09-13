from __future__ import annotations

from typing import Any

import pytest

from things_agent_workflow import server
from things_agent_workflow.models import HandoffKind, HandoffState, Ownership


class RecordingService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _record(self, name: str, values: dict[str, Any]) -> dict:
        self.calls.append((name, values))
        return {"called": name}

    def capture_handoff(self, **kwargs: Any) -> dict:
        return self._record("capture", kwargs)

    def resume_handoff(self, **kwargs: Any) -> dict:
        return self._record("resume", kwargs)

    def transition_handoff(self, **kwargs: Any) -> dict:
        return self._record("transition", kwargs)

    def review_handoffs(self, **kwargs: Any) -> dict:
        return self._record("review", kwargs)

    def build_workstream_project(self, **kwargs: Any) -> dict:
        return self._record("build", kwargs)


def test_tool_functions_forward_semantic_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = RecordingService()
    monkeypatch.setattr(server, "service", recording)

    assert server.capture_handoff(
        handoff_key="tooling:key",
        kind=HandoffKind.DECISION,
        ownership=Ownership.NICK_AGENT,
        title="choose",
        need_from_nick="Choose.",
        done_when="Recorded.",
        sources=["plan.md"],
    ) == {"called": "capture"}
    assert server.resume_handoff(task_id="task-1") == {"called": "resume"}
    assert server.transition_handoff(
        task_id="task-1", state=HandoffState.READY, when="today"
    ) == {"called": "transition"}
    assert server.review_handoffs(project_id="project-1", as_of="2026-09-12") == {
        "called": "review"
    }
    assert server.build_workstream_project(
        workstream_key="tooling:workflow",
        title="Workflow",
        purpose="Track human obligations.",
        closure_condition="All obligations are closed.",
        authoritative_sources=["plan.md"],
    ) == {"called": "build"}
    assert [name for name, _ in recording.calls] == [
        "capture",
        "resume",
        "transition",
        "review",
        "build",
    ]


def test_workflow_status_reports_non_sensitive_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StatusGateway:
        @staticmethod
        def list_tags() -> list[dict]:
            return [{"title": "waiting"}, {"title": "solo"}]

        @staticmethod
        def list_areas() -> list[dict]:
            return [{"uuid": "area-1"}]

        @staticmethod
        def list_projects() -> list[dict]:
            return [{"uuid": "project-1"}, {"uuid": "project-2"}]

    monkeypatch.setattr(server, "gateway", StatusGateway())

    status = server.workflow_status()

    assert status == {
        "read_access": True,
        "areas": 1,
        "projects": 2,
        "required_state_tags": {"waiting": True, "deferred": False},
        "optional_ownership_tags": {"solo": True, "build": False},
    }


def test_main_selects_stdio_or_http(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))
    monkeypatch.delenv("THINGS_AGENT_TRANSPORT", raising=False)

    server.main()
    assert calls.pop() == {}

    monkeypatch.setenv("THINGS_AGENT_TRANSPORT", "http")
    monkeypatch.setenv("THINGS_AGENT_HOST", "127.0.0.2")
    monkeypatch.setenv("THINGS_AGENT_PORT", "9013")
    server.main()
    assert calls.pop() == {"transport": "http", "host": "127.0.0.2", "port": 9013}
