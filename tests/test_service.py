from __future__ import annotations

import pytest
from conftest import FakeThingsGateway

from things_agent_workflow.models import (
    WORKSTREAM_HEADINGS,
    ConflictError,
    HandoffKind,
    HandoffState,
    Ownership,
    ValidationError,
    VerificationError,
)
from things_agent_workflow.notes import parse_notes
from things_agent_workflow.service import ThingsWorkflowService


def capture(
    service: ThingsWorkflowService,
    **overrides: object,
) -> dict:
    values = {
        "handoff_key": "tooling:crm-12345:choose-boundary",
        "kind": HandoffKind.DECISION,
        "ownership": Ownership.NICK_AGENT,
        "title": "choose the integration boundary",
        "need_from_nick": "Choose whether the service owns callbacks.",
        "agent_after": "Implement the selected boundary and run the checks.",
        "done_when": "The decision is recorded and the implementation passes.",
        "sources": ["~/source/example/docs/plan.md", "CRM-12345"],
        "project_title": "Things Agent Workflow",
    }
    values.update(overrides)
    return service.capture_handoff(**values)


def test_capture_creates_prefixed_verified_joint_handoff(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    receipt = capture(service)

    assert receipt["status"] == "created"
    assert receipt["verified"] is True
    assert receipt["item"]["title"] == "Decide: choose the integration boundary"
    assert receipt["item"]["tags"] == ["build"]
    assert gateway.add_calls[0]["list_id"] == "project-workflow"
    assert gateway.add_calls[0]["heading_id"] == "heading-0"
    assert receipt["item"]["project"] is None
    assert receipt["item"]["heading"] == "heading-0"
    assert receipt["metadata"]["project_id"] == "project-workflow"
    assert receipt["deep_link"] == "things:///show?id=task-1"


def test_capture_is_duplicate_safe_by_handoff_key(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    first = capture(service)
    second = capture(service, title="a different title that must not create another task")

    assert first["item"]["uuid"] == second["item"]["uuid"]
    assert second["status"] == "existing"
    assert len(gateway.add_calls) == 1


def test_capture_rejects_agent_only_ownership(service: ThingsWorkflowService) -> None:
    with pytest.raises(ValueError):
        Ownership("agent")


def test_joint_handoff_requires_agent_follow_through(service: ThingsWorkflowService) -> None:
    with pytest.raises(ValidationError, match="agent_after"):
        capture(service, agent_after=None)


def test_waiting_requires_next_check_before_write(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    with pytest.raises(ValidationError, match="next_check"):
        capture(service, state=HandoffState.WAITING)
    assert gateway.add_calls == []


def test_deferred_event_trigger_uses_someday_and_tag(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    receipt = capture(
        service,
        state=HandoffState.DEFERRED,
        revisit_trigger="FedRAMP environments become active",
    )

    assert receipt["item"]["start"] == "Someday"
    assert receipt["item"]["tags"] == ["build", "deferred"]
    assert receipt["metadata"]["revisit_trigger"] == "FedRAMP environments become active"


def test_unknown_person_tag_fails_before_write(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    with pytest.raises(ValidationError, match="existing Things tag"):
        capture(service, person_tag="@missing")
    assert gateway.add_calls == []


def test_message_transitions_to_follow_up_with_optimistic_check(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    created = capture(
        service,
        handoff_key="tooling:send-validation-packet",
        kind=HandoffKind.MESSAGE,
        title="validation packet to Damon",
    )
    resumed = service.resume_handoff(task_id=created["item"]["uuid"])

    updated = service.transition_handoff(
        task_id=created["item"]["uuid"],
        state=HandoffState.WAITING,
        expected_modified=resumed["expected_modified"],
        next_check="2026-09-15",
        person_tag="@damon",
    )

    assert updated["item"]["title"] == "Follow up: validation packet to Damon"
    assert updated["item"]["start_date"] == "2026-09-15"
    assert updated["item"]["tags"] == ["build", "waiting", "@damon"]
    assert updated["metadata"]["kind"] == "follow-up"
    assert updated["metadata"]["state"] == "waiting"


def test_transition_rejects_stale_modified_value(service: ThingsWorkflowService) -> None:
    created = capture(service)

    with pytest.raises(ConflictError, match="changed after it was read"):
        service.transition_handoff(
            task_id=created["item"]["uuid"],
            state=HandoffState.READY,
            expected_modified="stale-version",
        )


def test_complete_requires_and_preserves_durable_outcome(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    created = capture(service)

    with pytest.raises(ValidationError, match="completion_evidence"):
        service.transition_handoff(
            task_id=created["item"]["uuid"],
            state=HandoffState.COMPLETE,
            outcome="Selected callbacks.",
        )

    receipt = service.transition_handoff(
        task_id=created["item"]["uuid"],
        state=HandoffState.COMPLETE,
        outcome="Selected callbacks.",
        completion_evidence="docs/architecture.md at commit abc1234",
    )

    assert receipt["item"]["status"] == "completed"
    task = gateway.get_task(created["item"]["uuid"])
    assert task is not None
    assert "Outcome:\nSelected callbacks." in task["notes"]
    assert "Completion evidence:\ndocs/architecture.md at commit abc1234" in task["notes"]


def test_review_groups_ready_waiting_and_deferred(service: ThingsWorkflowService) -> None:
    capture(service)
    capture(
        service,
        handoff_key="tooling:waiting",
        kind=HandoffKind.FOLLOW_UP,
        state=HandoffState.WAITING,
        next_check="2026-09-12",
        person_tag="@damon",
    )
    capture(
        service,
        handoff_key="tooling:deferred",
        state=HandoffState.DEFERRED,
        revisit_on="2026-09-13",
    )

    review = service.review_handoffs(as_of="2026-09-12")

    assert review["counts"]["decisions"] == 1
    assert review["counts"]["waiting_due"] == 1
    assert review["counts"]["deferred_parked"] == 1


def test_workstream_builder_creates_standard_headings_once(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    first = service.build_workstream_project(
        workstream_key="tooling:new-workstream",
        title="New Workstream",
        purpose="Track human control points for the workstream.",
        closure_condition="No open human obligations remain.",
        authoritative_sources=["~/source/new-workstream"],
        area_title="Tooling",
    )
    second = service.build_workstream_project(
        workstream_key="tooling:new-workstream",
        title="Ignored duplicate title",
        purpose="Ignored duplicate purpose.",
        closure_condition="Ignored duplicate closure.",
        authoritative_sources=["~/source/ignored"],
        area_title="Tooling",
    )

    assert first["status"] == "created"
    assert first["project"]["headings"] == list(WORKSTREAM_HEADINGS)
    assert second["status"] == "existing"
    assert second["project"]["uuid"] == first["project"]["uuid"]
    assert len(gateway.json_calls) == 1
    project = gateway.list_projects()[-1]
    parsed = parse_notes(project["notes"])
    assert parsed is not None
    assert parsed.metadata["workstream_key"] == "tooling:new-workstream"


def test_resume_requires_exactly_one_identity(service: ThingsWorkflowService) -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        service.resume_handoff()
    with pytest.raises(ValidationError, match="exactly one"):
        service.resume_handoff(handoff_key="tooling:key", task_id="task-1")


def test_capture_supports_nick_only_area_and_inbox_destinations(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    area_receipt = capture(
        service,
        handoff_key="tooling:area-task",
        ownership=Ownership.NICK,
        agent_after=None,
        area_title="Tooling",
        project_title=None,
        when="2026-09-14@09:30",
        deadline="2026-09-15",
        person_tag="@damon",
    )
    gateway.tags = [tag for tag in gateway.tags if tag["title"] != "solo"]
    inbox_receipt = capture(
        service,
        handoff_key="tooling:inbox-task",
        ownership=Ownership.NICK,
        agent_after=None,
        project_title=None,
    )

    assert area_receipt["item"]["area"] == "area-tooling"
    assert area_receipt["item"]["deadline"] == "2026-09-15"
    assert area_receipt["item"]["tags"] == ["solo", "@damon"]
    assert inbox_receipt["item"]["project"] is None
    assert inbox_receipt["item"]["tags"] == []


def test_capture_validates_destinations_and_terminal_state(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    with pytest.raises(ValidationError, match="exactly one project or area"):
        capture(service, project_title="Things Agent Workflow", area_title="Tooling")
    with pytest.raises(ValidationError, match="resolve exactly one"):
        capture(service, project_title="Missing")
    with pytest.raises(ValidationError, match="already completed"):
        capture(service, project_title=None, state=HandoffState.COMPLETE)
    assert gateway.add_calls == []


def test_capture_verification_failure_is_not_reported_as_success(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    gateway.add_todo = lambda _params: None  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        capture(service)


def test_capture_verification_rejects_dropped_things_fields(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    original_add = gateway.add_todo

    def drop_tags(params: dict) -> None:
        original_add(params)
        gateway.tasks[-1]["tags"] = []

    gateway.add_todo = drop_tags  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        capture(service)


def test_capture_verification_rejects_changed_title(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    original_add = gateway.add_todo

    def change_title(params: dict) -> None:
        original_add(params)
        gateway.tasks[-1]["title"] = "Unexpected title"

    gateway.add_todo = change_title  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        capture(service)


def test_capture_verification_rejects_dropped_reminder_time(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    original_add = gateway.add_todo

    def drop_reminder_time(params: dict) -> None:
        original_add(params)
        gateway.tasks[-1]["reminder_time"] = None

    gateway.add_todo = drop_reminder_time  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        capture(service, when="2026-09-14@09:00")


@pytest.mark.parametrize(
    ("when", "expected_start_date", "expected_reminder_time"),
    [
        ("tomorrow", "2026-09-13", None),
        ("evening", "2026-09-12", None),
        ("2026-09-14@09:00", "2026-09-14", "09:00"),
    ],
)
def test_capture_verifies_relative_schedule_dates(
    service: ThingsWorkflowService,
    when: str,
    expected_start_date: str,
    expected_reminder_time: str | None,
) -> None:
    receipt = capture(
        service,
        handoff_key=f"tooling:schedule:{when.replace('@', '-')}",
        when=when,
    )

    assert receipt["item"]["start_date"] == expected_start_date
    assert receipt["item"]["reminder_time"] == expected_reminder_time


def test_transition_covers_deferred_ready_and_non_message_waiting(
    service: ThingsWorkflowService,
) -> None:
    created = capture(service, person_tag="@damon")

    with pytest.raises(ValidationError, match="revisit_on"):
        service.transition_handoff(
            task_id=created["item"]["uuid"], state=HandoffState.DEFERRED
        )

    deferred = service.transition_handoff(
        handoff_key="tooling:crm-12345:choose-boundary",
        state=HandoffState.DEFERRED,
        revisit_on="2026-09-20",
        person_tag="@damon",
    )
    assert deferred["item"]["tags"] == ["build", "deferred", "@damon"]

    ready = service.transition_handoff(
        task_id=created["item"]["uuid"],
        state=HandoffState.READY,
        when="today",
    )
    assert ready["item"]["tags"] == ["build"]
    assert ready["item"]["start_date"] == "2026-09-12"

    with pytest.raises(ValidationError, match="next_check"):
        service.transition_handoff(
            task_id=created["item"]["uuid"], state=HandoffState.WAITING
        )

    waiting = service.transition_handoff(
        task_id=created["item"]["uuid"],
        state=HandoffState.WAITING,
        next_check="2026-09-16",
    )
    assert waiting["item"]["title"].startswith("Decide:")
    assert waiting["item"]["tags"] == ["build", "waiting"]


def test_transition_rejects_unknown_state_and_unverified_write(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    created = capture(service)
    with pytest.raises(ValidationError, match="unsupported"):
        service.transition_handoff(  # type: ignore[arg-type]
            task_id=created["item"]["uuid"], state="unknown"
        )

    original_update = gateway.update_todo

    def discard_notes(task_id: str, changes: dict) -> None:
        original_update(task_id, {key: value for key, value in changes.items() if key != "notes"})

    gateway.update_todo = discard_notes  # type: ignore[method-assign]
    with pytest.raises(VerificationError, match="do not retry"):
        service.transition_handoff(
            task_id=created["item"]["uuid"],
            state=HandoffState.READY,
        )


def test_transition_verification_rejects_dropped_state_fields(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    created = capture(service)
    original_update = gateway.update_todo

    def keep_only_notes(task_id: str, changes: dict) -> None:
        original_update(task_id, {"notes": changes["notes"]})

    gateway.update_todo = keep_only_notes  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        service.transition_handoff(
            task_id=created["item"]["uuid"],
            state=HandoffState.WAITING,
            next_check="2026-09-16",
        )


def test_review_covers_all_ready_groups_dates_and_project_filter(
    service: ThingsWorkflowService,
) -> None:
    kinds = [
        HandoffKind.MESSAGE,
        HandoffKind.REVIEW,
        HandoffKind.APPROVAL,
        HandoffKind.UNBLOCK,
        HandoffKind.PUBLISH,
        HandoffKind.JOINT,
    ]
    for index, kind in enumerate(kinds):
        capture(
            service,
            handoff_key=f"tooling:review:{index}",
            kind=kind,
            project_title=None if index == 0 else "Things Agent Workflow",
        )
    capture(
        service,
        handoff_key="tooling:waiting-later",
        state=HandoffState.WAITING,
        next_check="2026-09-20",
    )
    capture(
        service,
        handoff_key="tooling:deferred-due",
        state=HandoffState.DEFERRED,
        revisit_on="2026-09-11",
    )

    review = service.review_handoffs(as_of="2026-09-12")
    project_review = service.review_handoffs(
        project_id="project-workflow", as_of="2026-09-12"
    )

    assert review["counts"]["messages"] == 1
    assert review["counts"]["reviews_and_approvals"] == 2
    assert review["counts"]["problems_to_unblock"] == 1
    assert review["counts"]["joint_follow_through"] == 2
    assert review["counts"]["waiting_later"] == 1
    assert review["counts"]["deferred_due"] == 1
    assert project_review["counts"]["messages"] == 0
    with pytest.raises(ValidationError, match="as_of"):
        service.review_handoffs(as_of="September 12")


def test_workstream_builder_validates_area_size_and_readback(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    with pytest.raises(ValidationError, match="not both"):
        service.build_workstream_project(
            workstream_key="tooling:bad-area",
            title="Bad",
            purpose="Purpose.",
            closure_condition="Closed.",
            authoritative_sources=["source"],
            area_id="area-tooling",
            area_title="Tooling",
        )
    with pytest.raises(ValidationError, match="10,000-character"):
        service.build_workstream_project(
            workstream_key="tooling:long-project",
            title="Long",
            purpose="x" * 4_000,
            closure_condition="y" * 4_000,
            authoritative_sources=["z" * 1_000, "q" * 1_000, "r" * 1_000],
        )

    gateway.create_json = lambda _payload: None  # type: ignore[method-assign]
    with pytest.raises(VerificationError, match="do not retry"):
        service.build_workstream_project(
            workstream_key="tooling:unverified-project",
            title="Unverified",
            purpose="Purpose.",
            closure_condition="Closed.",
            authoritative_sources=["source"],
            area_id="area-tooling",
        )


def test_workstream_verification_rejects_missing_heading(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    original_create = gateway.create_json

    def omit_heading(payload: list[dict]) -> None:
        original_create(payload)
        gateway.projects[-1]["items"].pop()

    gateway.create_json = omit_heading  # type: ignore[method-assign]

    with pytest.raises(VerificationError, match="do not retry"):
        service.build_workstream_project(
            workstream_key="tooling:missing-heading",
            title="Missing Heading",
            purpose="Verify every requested project field.",
            closure_condition="All headings are present.",
            authoritative_sources=["source"],
            area_title="Tooling",
        )


def test_duplicate_managed_identities_fail_closed(
    service: ThingsWorkflowService, gateway: FakeThingsGateway
) -> None:
    created = capture(service)
    duplicate = gateway.get_task(created["item"]["uuid"])
    assert duplicate is not None
    duplicate["uuid"] = "task-duplicate"
    gateway.tasks.append(duplicate)

    with pytest.raises(ConflictError, match="more than one Things task"):
        capture(service)

    service.build_workstream_project(
        workstream_key="tooling:duplicate-project",
        title="Duplicate Project",
        purpose="Purpose.",
        closure_condition="Closed.",
        authoritative_sources=["source"],
    )
    duplicate_project = gateway.projects[-1].copy()
    duplicate_project["uuid"] = "project-duplicate"
    gateway.projects.append(duplicate_project)
    with pytest.raises(ConflictError, match="more than one Things project"):
        service.build_workstream_project(
            workstream_key="tooling:duplicate-project",
            title="Duplicate Project",
            purpose="Purpose.",
            closure_condition="Closed.",
            authoritative_sources=["source"],
        )
