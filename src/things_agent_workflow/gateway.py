from __future__ import annotations

import subprocess
from collections.abc import Mapping
from typing import Any, Protocol

import things

from .models import ValidationError
from .urls import add_todo_url, json_url, update_todo_url


class ThingsGateway(Protocol):
    def search_tasks(self, query: str) -> list[dict[str, Any]]: ...

    def list_tasks(self) -> list[dict[str, Any]]: ...

    def get_task(self, task_id: str) -> dict[str, Any] | None: ...

    def list_projects(self) -> list[dict[str, Any]]: ...

    def list_areas(self) -> list[dict[str, Any]]: ...

    def list_tags(self) -> list[dict[str, Any]]: ...

    def list_headings(self, project_id: str) -> list[dict[str, Any]]: ...

    def add_todo(self, params: Mapping[str, Any]) -> None: ...

    def update_todo(self, task_id: str, changes: Mapping[str, Any]) -> None: ...

    def create_json(self, payload: list[dict[str, Any]]) -> None: ...


class RealThingsGateway:
    """Read through things-py and write through the documented Things URL scheme."""

    def search_tasks(self, query: str) -> list[dict[str, Any]]:
        return list(things.tasks(status=None, search_query=query, include_items=True) or [])

    def list_tasks(self) -> list[dict[str, Any]]:
        return list(things.tasks(status="incomplete", include_items=True) or [])

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        matches = list(things.tasks(status=None, include_items=True) or [])
        return next((task for task in matches if task.get("uuid") == task_id), None)

    def list_projects(self) -> list[dict[str, Any]]:
        return list(things.projects(status=None, include_items=True) or [])

    def list_areas(self) -> list[dict[str, Any]]:
        return list(things.areas(include_items=False) or [])

    def list_tags(self) -> list[dict[str, Any]]:
        return list(things.tags(include_items=False) or [])

    def list_headings(self, project_id: str) -> list[dict[str, Any]]:
        return list(things.tasks(type="heading", project=project_id, status=None) or [])

    def add_todo(self, params: Mapping[str, Any]) -> None:
        url = add_todo_url(**params)
        self._open(url)

    def update_todo(self, task_id: str, changes: Mapping[str, Any]) -> None:
        token = things.token()
        if not token:
            raise ValidationError(
                "Things URL authorization is not enabled; updates require the local auth token"
            )
        url = update_todo_url(task_id=task_id, auth_token=token, changes=changes)
        self._open(url)

    def create_json(self, payload: list[dict[str, Any]]) -> None:
        self._open(json_url(payload))

    @staticmethod
    def _open(url: str) -> None:
        escaped_url = url.replace("\\", "\\\\").replace('"', '\\"')
        script = f'do shell script "/usr/bin/open -g " & quoted form of "{escaped_url}"'
        subprocess.run(
            ["osascript"],
            check=True,
            capture_output=True,
            text=True,
            input=script,
        )
