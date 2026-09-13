from __future__ import annotations

import pytest

from things_agent_workflow.models import ConflictError, ValidationError
from things_agent_workflow.notes import append_outcome, build_notes, parse_notes, replace_metadata


def test_build_and_parse_notes_preserve_human_packet() -> None:
    metadata = {"schema": 1, "record_type": "handoff", "handoff_key": "tooling:decision"}

    notes = build_notes(
        metadata,
        need_from_nick="Choose A or B.",
        agent_after="Implement the choice.",
        done_when="The contract and code agree.",
        sources=["~/source/example/plan.md", "CRM-12345"],
        recheck="Verify the current branch.",
        additional_notes="Option A is cheaper.",
    )

    parsed = parse_notes(notes)
    assert parsed is not None
    assert parsed.metadata == metadata
    assert "Need from Nick:\nChoose A or B." in parsed.body
    assert "- CRM-12345" in parsed.body


def test_replace_metadata_preserves_packet() -> None:
    notes = build_notes(
        {"schema": 1, "state": "ready"},
        need_from_nick="Choose.",
        agent_after=None,
        done_when="Recorded.",
        sources=[],
        recheck=None,
        additional_notes=None,
    )

    updated = replace_metadata(notes, {"schema": 1, "state": "waiting"})

    parsed = parse_notes(updated)
    assert parsed is not None
    assert parsed.metadata["state"] == "waiting"
    assert parsed.body.endswith("Done when:\nRecorded.")


def test_parse_rejects_broken_managed_block() -> None:
    with pytest.raises(ConflictError, match="without an end marker"):
        parse_notes("[things-agent-workflow]\n{}")


def test_parse_ignores_unmanaged_notes_and_rejects_invalid_metadata() -> None:
    assert parse_notes("ordinary notes") is None
    with pytest.raises(ConflictError, match="valid JSON"):
        parse_notes("[things-agent-workflow]\n{broken}\n[/things-agent-workflow]")
    with pytest.raises(ConflictError, match="schema"):
        parse_notes("[things-agent-workflow]\n{}\n[/things-agent-workflow]")


def test_replace_rejects_unmanaged_notes() -> None:
    with pytest.raises(ConflictError, match="not managed"):
        replace_metadata("ordinary notes", {"schema": 1})


def test_build_rejects_notes_over_things_limit() -> None:
    with pytest.raises(ValidationError, match="10,000-character"):
        build_notes(
            {"schema": 1},
            need_from_nick="x" * 10_001,
            agent_after=None,
            done_when="Done.",
            sources=[],
            recheck=None,
            additional_notes=None,
        )


def test_append_outcome_rejects_notes_over_things_limit() -> None:
    with pytest.raises(ValidationError, match="10,000-character"):
        append_outcome("x" * 9_990, "outcome", "evidence")
