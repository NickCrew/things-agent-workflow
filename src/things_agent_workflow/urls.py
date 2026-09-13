from __future__ import annotations

import json
import urllib.parse
from collections.abc import Mapping
from typing import Any


def _encoded(value: Any) -> str:
    if isinstance(value, bool):
        value = str(value).lower()
    return urllib.parse.quote(str(value), safe="")


def build_url(command: str, params: Mapping[str, Any]) -> str:
    encoded = [f"{key}={_encoded(value)}" for key, value in params.items() if value is not None]
    base = f"things:///{command}"
    return f"{base}?{'&'.join(encoded)}" if encoded else base


def add_todo_url(
    *,
    title: str,
    notes: str,
    when: str | None,
    deadline: str | None,
    tags: list[str],
    list_id: str | None,
    heading_id: str | None,
) -> str:
    return build_url(
        "add",
        {
            "title": title,
            "notes": notes,
            "when": when,
            "deadline": deadline,
            "tags": ",".join(tags) if tags else None,
            "list-id": list_id,
            "heading-id": heading_id,
        },
    )


def update_todo_url(*, task_id: str, auth_token: str, changes: Mapping[str, Any]) -> str:
    params = {"id": task_id, "auth-token": auth_token, **changes}
    if params.get("when") == "anytime":
        params["when"] = ""
    if isinstance(params.get("tags"), list):
        params["tags"] = ",".join(params["tags"])
    return build_url("update", params)


def json_url(payload: list[dict[str, Any]], auth_token: str | None = None) -> str:
    params: dict[str, Any] = {
        "data": json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
    }
    if auth_token:
        params["auth-token"] = auth_token
    return build_url("json", params)


def deep_link(item_id: str) -> str:
    return build_url("show", {"id": item_id})
