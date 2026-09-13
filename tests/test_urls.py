from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from things_agent_workflow.urls import add_todo_url, build_url, json_url, update_todo_url


def query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query, keep_blank_values=True)


def test_add_todo_url_encodes_managed_fields() -> None:
    url = add_todo_url(
        title="Decide: A/B",
        notes="line one\nline two",
        when="2026-09-15@14:30",
        deadline=None,
        tags=["build", "@damon"],
        list_id="project/one",
        heading_id="heading-one",
    )

    assert url.startswith("things:///add?")
    assert query(url) == {
        "title": ["Decide: A/B"],
        "notes": ["line one\nline two"],
        "when": ["2026-09-15@14:30"],
        "tags": ["build,@damon"],
        "list-id": ["project/one"],
        "heading-id": ["heading-one"],
    }


def test_update_url_preserves_explicit_clear_and_encodes_token() -> None:
    url = update_todo_url(
        task_id="task-one",
        auth_token="secret/value",
        changes={"deadline": "", "tags": ["waiting", "@damon"]},
    )

    assert query(url) == {
        "id": ["task-one"],
        "auth-token": ["secret/value"],
        "deadline": [""],
        "tags": ["waiting,@damon"],
    }


def test_update_url_translates_anytime_to_a_cleared_when_value() -> None:
    url = update_todo_url(
        task_id="task-one",
        auth_token="secret/value",
        changes={"when": "anytime"},
    )

    assert query(url)["when"] == [""]


def test_json_url_encodes_structured_project() -> None:
    payload = [{"type": "project", "attributes": {"title": "Control plane"}}]

    url = json_url(payload)

    assert query(url)["data"] == [
        '[{"type":"project","attributes":{"title":"Control plane"}}]'
    ]


def test_url_helpers_cover_boolean_empty_and_authenticated_json() -> None:
    assert build_url("version", {}) == "things:///version"
    assert query(build_url("add", {"completed": True})) == {"completed": ["true"]}
    assert query(json_url([], auth_token="secret"))["auth-token"] == ["secret"]
