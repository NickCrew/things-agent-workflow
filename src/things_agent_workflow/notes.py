from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .models import ConflictError, ValidationError

START_MARKER = "[things-agent-workflow]"
END_MARKER = "[/things-agent-workflow]"
MAX_NOTES_LENGTH = 10_000


@dataclass(frozen=True)
class ManagedNotes:
    metadata: dict[str, Any]
    body: str


def render_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def build_notes(
    metadata: dict[str, Any],
    *,
    need_from_nick: str,
    agent_after: str | None,
    done_when: str,
    sources: list[str],
    recheck: str | None,
    additional_notes: str | None,
) -> str:
    sections = [
        START_MARKER,
        render_metadata(metadata),
        END_MARKER,
        "",
        "Need from Nick:",
        need_from_nick.strip(),
    ]
    if agent_after:
        sections.extend(["", "Agent after:", agent_after.strip()])
    sections.extend(["", "Done when:", done_when.strip()])
    if sources:
        sections.extend(["", "Sources:", *(f"- {source.strip()}" for source in sources)])
    if recheck:
        sections.extend(["", "Recheck:", recheck.strip()])
    if additional_notes:
        sections.extend(["", "Context:", additional_notes.strip()])
    result = "\n".join(sections).rstrip()
    if len(result) > MAX_NOTES_LENGTH:
        raise ValidationError("managed notes exceed the Things 10,000-character limit")
    return result


def parse_notes(notes: str | None) -> ManagedNotes | None:
    if not notes or START_MARKER not in notes:
        return None
    start = notes.find(START_MARKER)
    end = notes.find(END_MARKER, start + len(START_MARKER))
    if end < 0:
        raise ConflictError("managed note start marker exists without an end marker")
    raw = notes[start + len(START_MARKER) : end].strip()
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConflictError("managed note metadata is not valid JSON") from exc
    if not isinstance(metadata, dict) or metadata.get("schema") != 1:
        raise ConflictError("managed note schema is missing or unsupported")
    body = notes[end + len(END_MARKER) :].lstrip("\n")
    return ManagedNotes(metadata=metadata, body=body)


def replace_metadata(notes: str, metadata: dict[str, Any]) -> str:
    parsed = parse_notes(notes)
    if parsed is None:
        raise ConflictError("task is not managed by things-agent-workflow")
    result = f"{START_MARKER}\n{render_metadata(metadata)}\n{END_MARKER}"
    if parsed.body:
        result += f"\n\n{parsed.body}"
    if len(result) > MAX_NOTES_LENGTH:
        raise ValidationError("managed notes exceed the Things 10,000-character limit")
    return result


def append_outcome(notes: str, outcome: str, evidence: str) -> str:
    result = (
        f"{notes.rstrip()}\n\nOutcome:\n{outcome.strip()}"
        f"\n\nCompletion evidence:\n{evidence.strip()}"
    )
    if len(result) > MAX_NOTES_LENGTH:
        raise ValidationError("managed notes exceed the Things 10,000-character limit")
    return result
