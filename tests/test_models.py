from __future__ import annotations

import pytest

from things_agent_workflow.models import (
    HandoffKind,
    ValidationError,
    prefixed_title,
    validate_date,
    validate_handoff_key,
    validate_nonempty,
    validate_when,
)


@pytest.mark.parametrize("value", ["Key", "ab", "bad key", "bad@key", "x" * 201])
def test_handoff_key_rejects_unstable_forms(value: str) -> None:
    with pytest.raises(ValidationError, match="handoff_key"):
        validate_handoff_key(value)


def test_basic_validation_accepts_supported_values() -> None:
    assert validate_handoff_key("tooling:crm-123") == "tooling:crm-123"
    assert validate_nonempty("value", "  text  ") == "text"
    assert validate_date("date", None) is None
    assert validate_date("date", "2026-09-12") == "2026-09-12"
    assert validate_when("today") == "today"
    assert validate_when("2026-09-12@09:30") == "2026-09-12@09:30"
    assert validate_when(None) is None
    assert prefixed_title(HandoffKind.DECISION, "Decide: keep it") == "Decide: keep it"
    assert prefixed_title(HandoffKind.TASK, "Buy milk") == "Buy milk"


def test_basic_validation_rejects_empty_long_and_invalid_dates() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        validate_nonempty("value", " ")
    with pytest.raises(ValidationError, match="no longer"):
        validate_nonempty("value", "abc", maximum=2)
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        validate_date("date", "09/12/2026")
    with pytest.raises(ValidationError, match="when must"):
        validate_when("next week")
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        validate_when("2026-02-30@09:00")
