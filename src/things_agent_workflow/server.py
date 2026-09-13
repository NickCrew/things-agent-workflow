from __future__ import annotations

import os
from typing import Literal

from fastmcp import FastMCP

from .gateway import RealThingsGateway
from .models import HandoffKind, HandoffState, Ownership
from .service import ThingsWorkflowService

mcp = FastMCP("Things Agent Workflow")
gateway = RealThingsGateway()
service = ThingsWorkflowService(gateway)


@mcp.tool
def capture_handoff(
    handoff_key: str,
    kind: HandoffKind,
    ownership: Ownership,
    title: str,
    need_from_nick: str,
    done_when: str,
    agent_after: str | None = None,
    sources: list[str] | None = None,
    recheck: str | None = None,
    additional_notes: str | None = None,
    state: HandoffState = HandoffState.READY,
    when: str | None = None,
    deadline: str | None = None,
    next_check: str | None = None,
    revisit_on: str | None = None,
    revisit_trigger: str | None = None,
    person_tag: str | None = None,
    project_id: str | None = None,
    project_title: str | None = None,
    area_id: str | None = None,
    area_title: str | None = None,
) -> dict:
    """Capture one Nick-only or Nick-plus-agent obligation in Things.

    Use only after the user explicitly asks to track, defer, park, or remember the
    obligation. Never use this for agent-only work or as a Jira substitute. The
    stable handoff_key prevents duplicate capture across parallel sessions.
    """
    return service.capture_handoff(
        handoff_key=handoff_key,
        kind=kind,
        ownership=ownership,
        title=title,
        need_from_nick=need_from_nick,
        done_when=done_when,
        agent_after=agent_after,
        sources=sources,
        recheck=recheck,
        additional_notes=additional_notes,
        state=state,
        when=when,
        deadline=deadline,
        next_check=next_check,
        revisit_on=revisit_on,
        revisit_trigger=revisit_trigger,
        person_tag=person_tag,
        project_id=project_id,
        project_title=project_title,
        area_id=area_id,
        area_title=area_title,
    )


@mcp.tool
def resume_handoff(
    handoff_key: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Read one managed handoff and return its human-agent packet.

    Provide exactly one stable handoff key or Things item ID. Treat source facts in
    the packet as context to revalidate, not as proof of current repository, Jira,
    deployment, or runtime state.
    """
    return service.resume_handoff(handoff_key=handoff_key, task_id=task_id)


@mcp.tool
def transition_handoff(
    state: HandoffState,
    handoff_key: str | None = None,
    task_id: str | None = None,
    expected_modified: str | None = None,
    when: str | None = None,
    next_check: str | None = None,
    revisit_on: str | None = None,
    revisit_trigger: str | None = None,
    person_tag: str | None = None,
    outcome: str | None = None,
    completion_evidence: str | None = None,
) -> dict:
    """Move a managed handoff to ready, waiting, deferred, or complete.

    Waiting requires a next-check date. Deferred requires a date or event trigger.
    Complete requires the outcome and its durable evidence. Pass expected_modified
    from resume_handoff to reject stale concurrent updates.
    """
    return service.transition_handoff(
        state=state,
        handoff_key=handoff_key,
        task_id=task_id,
        expected_modified=expected_modified,
        when=when,
        next_check=next_check,
        revisit_on=revisit_on,
        revisit_trigger=revisit_trigger,
        person_tag=person_tag,
        outcome=outcome,
        completion_evidence=completion_evidence,
    )


@mcp.tool
def review_handoffs(project_id: str | None = None, as_of: str | None = None) -> dict:
    """Review managed human obligations without changing Things.

    Optionally limit the result to one Things project. Waiting and deferred items
    remain suppressed until their date is due; event-triggered deferred items stay
    parked for explicit weekly or context-aware review.
    """
    return service.review_handoffs(project_id=project_id, as_of=as_of)


@mcp.tool
def build_workstream_project(
    workstream_key: str,
    title: str,
    purpose: str,
    closure_condition: str,
    authoritative_sources: list[str],
    area_id: str | None = None,
    area_title: str | None = None,
    when: str = "anytime",
) -> dict:
    """Build one durable Things workstream for human-side agent coordination.

    The project contains standard headings for decisions, and other human control
    points. It does not copy Jira issues or create agent-only tasks. Project creation
    requires an explicit user request and a stable workstream key.
    """
    return service.build_workstream_project(
        workstream_key=workstream_key,
        title=title,
        purpose=purpose,
        closure_condition=closure_condition,
        authoritative_sources=authoritative_sources,
        area_id=area_id,
        area_title=area_title,
        when=when,
    )


@mcp.tool
def workflow_status() -> dict:
    """Check read access and report non-sensitive workflow prerequisites."""
    tags = {item.get("title") for item in gateway.list_tags()}
    return {
        "read_access": True,
        "areas": len(gateway.list_areas()),
        "projects": len(gateway.list_projects()),
        "required_state_tags": {
            "waiting": "waiting" in tags,
            "deferred": "deferred" in tags,
        },
        "optional_ownership_tags": {
            "solo": "solo" in tags,
            "build": "build" in tags,
        },
    }


def main() -> None:
    transport: Literal["stdio", "http"] = (
        "http" if os.environ.get("THINGS_AGENT_TRANSPORT") == "http" else "stdio"
    )
    if transport == "http":
        host = os.environ.get("THINGS_AGENT_HOST", "127.0.0.1")
        port = int(os.environ.get("THINGS_AGENT_PORT", "8013"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
