from __future__ import annotations

import subprocess

import pytest

from things_agent_workflow import gateway as gateway_module
from things_agent_workflow.gateway import RealThingsGateway
from things_agent_workflow.models import ValidationError


def test_read_gateway_delegates_to_things_database(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    def tasks(**kwargs: object) -> list[dict]:
        calls.append(("tasks", kwargs))
        return [{"uuid": "task-1"}]

    monkeypatch.setattr(gateway_module.things, "tasks", tasks)
    monkeypatch.setattr(
        gateway_module.things,
        "projects",
        lambda **kwargs: [{"uuid": "project-1", "kwargs": kwargs}],
    )
    monkeypatch.setattr(
        gateway_module.things, "areas", lambda **kwargs: [{"uuid": "area-1", "kwargs": kwargs}]
    )
    monkeypatch.setattr(
        gateway_module.things, "tags", lambda **kwargs: [{"title": "waiting", "kwargs": kwargs}]
    )
    gateway = RealThingsGateway()

    assert gateway.search_tasks("key") == [{"uuid": "task-1"}]
    assert gateway.list_tasks() == [{"uuid": "task-1"}]
    assert gateway.get_task("task-1") == {"uuid": "task-1"}
    assert gateway.get_task("missing") is None
    assert gateway.list_projects()[0]["uuid"] == "project-1"
    assert gateway.list_areas()[0]["uuid"] == "area-1"
    assert gateway.list_tags()[0]["title"] == "waiting"
    assert gateway.list_headings("project-1") == [{"uuid": "task-1"}]
    assert ("tasks", {"status": None, "search_query": "key", "include_items": True}) in calls
    assert (
        "tasks",
        {"type": "heading", "project": "project-1", "status": None},
    ) in calls


def test_update_requires_local_things_authorization_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_module.things, "token", lambda: None)

    with pytest.raises(ValidationError, match="authorization"):
        RealThingsGateway().update_todo("task-1", {"when": "today"})


def test_write_gateway_passes_url_through_osascript_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed: list[tuple[list[str], dict]] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        completed.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gateway_module.subprocess, "run", run)
    monkeypatch.setattr(gateway_module.things, "token", lambda: "secret/value")
    gateway = RealThingsGateway()

    gateway.add_todo(
        {
            "title": "Decide: boundary",
            "notes": "packet",
            "when": "today",
            "deadline": None,
            "tags": ["build"],
            "list_id": None,
            "heading_id": None,
        }
    )
    gateway.update_todo("task-1", {"deadline": ""})
    gateway.create_json([{"type": "project", "attributes": {"title": "Workstream"}}])

    assert len(completed) == 3
    for argv, kwargs in completed:
        assert argv == ["osascript"]
        assert "things:///" not in " ".join(argv)
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
    assert "things:///add?" in completed[0][1]["input"]
    assert "auth-token=secret%2Fvalue" in completed[1][1]["input"]
    assert "deadline=" in completed[1][1]["input"]
    assert "things:///json?" in completed[2][1]["input"]
