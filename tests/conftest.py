from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from things_agent_workflow.models import WORKSTREAM_HEADINGS
from things_agent_workflow.service import ThingsWorkflowService


class FakeThingsGateway:
    def __init__(self) -> None:
        self.tags = [
            {"uuid": "tag-solo", "title": "solo"},
            {"uuid": "tag-build", "title": "build"},
            {"uuid": "tag-waiting", "title": "waiting"},
            {"uuid": "tag-deferred", "title": "deferred"},
            {"uuid": "tag-damon", "title": "@damon"},
        ]
        self.areas = [{"uuid": "area-tooling", "title": "Tooling"}]
        self.headings = [
            {
                "uuid": f"heading-{index}",
                "type": "heading",
                "title": title,
                "project": "project-workflow",
            }
            for index, title in enumerate(WORKSTREAM_HEADINGS)
        ]
        self.projects = [
            {
                "uuid": "project-workflow",
                "type": "project",
                "title": "Things Agent Workflow",
                "notes": "",
                "status": "incomplete",
                "items": deepcopy(self.headings),
            }
        ]
        self.tasks: list[dict[str, Any]] = []
        self.add_calls: list[dict[str, Any]] = []
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
        self.json_calls: list[list[dict[str, Any]]] = []
        self._sequence = 0

    def search_tasks(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold()
        return [
            deepcopy(task)
            for task in self.tasks
            if needle in f"{task.get('title', '')}\n{task.get('notes', '')}".casefold()
        ]

    def list_tasks(self) -> list[dict[str, Any]]:
        return [deepcopy(task) for task in self.tasks if task["status"] == "incomplete"]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = next((task for task in self.tasks if task["uuid"] == task_id), None)
        return deepcopy(task) if task else None

    def list_projects(self) -> list[dict[str, Any]]:
        return deepcopy(self.projects)

    def list_areas(self) -> list[dict[str, Any]]:
        return deepcopy(self.areas)

    def list_tags(self) -> list[dict[str, Any]]:
        return deepcopy(self.tags)

    def list_headings(self, project_id: str) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self.headings if item["project"] == project_id]

    def add_todo(self, params: dict[str, Any]) -> None:
        self.add_calls.append(deepcopy(params))
        self._sequence += 1
        project_id = params.get("list_id")
        project = next((item for item in self.projects if item["uuid"] == project_id), None)
        heading = next(
            (item for item in self.headings if item["uuid"] == params.get("heading_id")),
            None,
        )
        task = {
            "uuid": f"task-{self._sequence}",
            "type": "to-do",
            "title": params["title"],
            "notes": params["notes"],
            "status": "incomplete",
            "tags": list(params.get("tags") or []),
            "project": project_id if project and heading is None else None,
            "project_title": project["title"] if project and heading is None else None,
            "area": params.get("list_id") if not project else None,
            "area_title": None,
            "heading": params.get("heading_id"),
            "heading_title": heading["title"] if heading else None,
            "deadline": params.get("deadline"),
            "modified": f"v{self._sequence}",
        }
        self._apply_when(task, params.get("when"))
        self.tasks.append(task)

    def update_todo(self, task_id: str, changes: dict[str, Any]) -> None:
        self.update_calls.append((task_id, deepcopy(changes)))
        task = next(task for task in self.tasks if task["uuid"] == task_id)
        for key in ("title", "notes", "tags", "deadline"):
            if key in changes:
                task[key] = deepcopy(changes[key])
        if "when" in changes:
            self._apply_when(task, changes["when"])
        if changes.get("completed") is True:
            task["status"] = "completed"
        self._sequence += 1
        task["modified"] = f"v{self._sequence}"

    def create_json(self, payload: list[dict[str, Any]]) -> None:
        self.json_calls.append(deepcopy(payload))
        attributes = payload[0]["attributes"]
        self._sequence += 1
        project_id = f"project-{self._sequence}"
        headings = [
            {
                "uuid": f"{project_id}-heading-{index}",
                "type": "heading",
                "title": item["attributes"]["title"],
                "project": project_id,
            }
            for index, item in enumerate(attributes["items"])
        ]
        project = {
            "uuid": project_id,
            "type": "project",
            "title": attributes["title"],
            "notes": attributes["notes"],
            "status": "incomplete",
            "area": attributes.get("area-id"),
            "area_title": "Tooling" if attributes.get("area-id") == "area-tooling" else None,
            "items": headings,
        }
        self._apply_when(project, attributes.get("when"))
        self.projects.append(project)
        self.headings.extend(headings)

    @staticmethod
    def _apply_when(task: dict[str, Any], when: str | None) -> None:
        task["start_date"] = None
        task["reminder_time"] = None
        if when == "someday":
            task["start"] = "Someday"
        elif when in {None, "anytime"}:
            task["start"] = "Anytime"
        elif when == "today":
            task["start"] = "Anytime"
            task["start_date"] = "2026-09-12"
        elif when == "tomorrow":
            task["start"] = "Anytime"
            task["start_date"] = "2026-09-13"
        elif when == "evening":
            task["start"] = "Anytime"
            task["start_date"] = "2026-09-12"
        else:
            task["start"] = "Anytime"
            task["start_date"], _, reminder_time = when.partition("@")
            task["reminder_time"] = reminder_time or None


@pytest.fixture
def gateway() -> FakeThingsGateway:
    return FakeThingsGateway()


@pytest.fixture
def service(gateway: FakeThingsGateway, tmp_path: Path) -> ThingsWorkflowService:
    return ThingsWorkflowService(
        gateway,
        lock_path=tmp_path / "write.lock",
        clock=lambda: datetime(2026, 9, 12, 16, 0, tzinfo=UTC),
        verification_timeout=0,
    )
