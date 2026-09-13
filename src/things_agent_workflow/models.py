from __future__ import annotations

import re
from datetime import date
from enum import StrEnum


class WorkflowError(RuntimeError):
    """Base error safe to return through MCP."""


class ValidationError(WorkflowError):
    """The requested handoff violates the workflow contract."""


class ConflictError(WorkflowError):
    """The target changed or has more than one managed identity."""


class VerificationError(WorkflowError):
    """A write was submitted but could not be verified."""


class HandoffKind(StrEnum):
    TASK = "task"
    DECISION = "decision"
    MESSAGE = "message"
    REVIEW = "review"
    APPROVAL = "approval"
    UNBLOCK = "unblock"
    FOLLOW_UP = "follow-up"
    PUBLISH = "publish"
    JOINT = "joint"


class Ownership(StrEnum):
    NICK = "nick"
    NICK_AGENT = "nick-agent"


class HandoffState(StrEnum):
    READY = "ready"
    WAITING = "waiting"
    DEFERRED = "deferred"
    COMPLETE = "complete"


HEADING_BY_KIND = {
    HandoffKind.TASK: "Joint follow-through",
    HandoffKind.DECISION: "Decisions",
    HandoffKind.MESSAGE: "Messages and asks",
    HandoffKind.FOLLOW_UP: "Messages and asks",
    HandoffKind.REVIEW: "Reviews and approvals",
    HandoffKind.APPROVAL: "Reviews and approvals",
    HandoffKind.UNBLOCK: "Problems to unblock",
    HandoffKind.PUBLISH: "Joint follow-through",
    HandoffKind.JOINT: "Joint follow-through",
}

TITLE_PREFIX_BY_KIND = {
    HandoffKind.TASK: "",
    HandoffKind.DECISION: "Decide",
    HandoffKind.MESSAGE: "Send",
    HandoffKind.REVIEW: "Review",
    HandoffKind.APPROVAL: "Approve",
    HandoffKind.UNBLOCK: "Unblock",
    HandoffKind.FOLLOW_UP: "Follow up",
    HandoffKind.PUBLISH: "Publish",
    HandoffKind.JOINT: "Continue with agent",
}

WORKSTREAM_HEADINGS = (
    "Decisions",
    "Messages and asks",
    "Reviews and approvals",
    "Problems to unblock",
    "Joint follow-through",
)

_HANDOFF_KEY = re.compile(r"^[a-z0-9][a-z0-9:._/-]{2,199}$")
_WHEN_KEYWORDS = {"today", "tomorrow", "evening", "anytime", "someday"}
_WHEN_DATE_TIME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:@([01]\d|2[0-3]):[0-5]\d)?$")


def validate_handoff_key(value: str) -> str:
    candidate = value.strip()
    if not _HANDOFF_KEY.fullmatch(candidate):
        raise ValidationError(
            "handoff_key must be 3-200 lowercase characters using letters, digits, :, ., _, /, or -"
        )
    return candidate


def validate_nonempty(label: str, value: str, maximum: int = 4_000) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValidationError(f"{label} must not be empty")
    if len(candidate) > maximum:
        raise ValidationError(f"{label} must be no longer than {maximum} characters")
    return candidate


def validate_date(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must use YYYY-MM-DD") from exc
    return value


def validate_when(value: str | None) -> str | None:
    if value is None:
        return None
    if value in _WHEN_KEYWORDS:
        return value
    match = _WHEN_DATE_TIME.fullmatch(value)
    if not match:
        raise ValidationError(
            "when must be today, tomorrow, evening, anytime, someday, YYYY-MM-DD, "
            "or YYYY-MM-DD@HH:MM"
        )
    validate_date("when date", match.group(1))
    return value


def prefixed_title(kind: HandoffKind, title: str) -> str:
    candidate = validate_nonempty("title", title, maximum=500)
    prefix = TITLE_PREFIX_BY_KIND[kind]
    if not prefix:
        return candidate
    if candidate.casefold().startswith(f"{prefix.casefold()}:"):
        return candidate
    return f"{prefix}: {candidate}"
