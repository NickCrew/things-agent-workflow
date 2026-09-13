from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .gateway import ThingsGateway
from .locking import exclusive_write_lock
from .models import (
    HEADING_BY_KIND,
    WORKSTREAM_HEADINGS,
    ConflictError,
    HandoffKind,
    HandoffState,
    Ownership,
    ValidationError,
    VerificationError,
    prefixed_title,
    validate_date,
    validate_handoff_key,
    validate_nonempty,
    validate_when,
)
from .notes import (
    END_MARKER,
    MAX_NOTES_LENGTH,
    START_MARKER,
    append_outcome,
    build_notes,
    parse_notes,
    render_metadata,
    replace_metadata,
)
from .urls import deep_link


class ThingsWorkflowService:
    def __init__(
        self,
        gateway: ThingsGateway,
        *,
        lock_path: Path | None = None,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        verification_timeout: float = 5.0,
    ) -> None:
        self.gateway = gateway
        self.lock_path = lock_path
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleeper = sleeper
        self.verification_timeout = verification_timeout

    def capture_handoff(
        self,
        *,
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
    ) -> dict[str, Any]:
        key = validate_handoff_key(handoff_key)
        full_title = prefixed_title(kind, title)
        need = validate_nonempty("need_from_nick", need_from_nick)
        done = validate_nonempty("done_when", done_when)
        if ownership is Ownership.NICK_AGENT and not agent_after:
            raise ValidationError("agent_after is required for nick-agent handoffs")
        if agent_after:
            agent_after = validate_nonempty("agent_after", agent_after)
        normalized_sources = self._normalize_sources(sources or [])
        when = validate_when(when)
        deadline = validate_date("deadline", deadline)
        next_check = validate_date("next_check", next_check)
        revisit_on = validate_date("revisit_on", revisit_on)
        now = self._timestamp()

        with exclusive_write_lock(self.lock_path):
            existing = self._find_handoff(key)
            if existing:
                return self._receipt("existing", existing)

            destination_id, resolved_project_id = self._resolve_destination(
                project_id=project_id,
                project_title=project_title,
                area_id=area_id,
                area_title=area_title,
            )
            heading_id = self._resolve_heading(resolved_project_id, HEADING_BY_KIND[kind])
            tags, scheduled_when = self._capture_state(
                state=state,
                ownership=ownership,
                when=when,
                next_check=next_check,
                revisit_on=revisit_on,
                revisit_trigger=revisit_trigger,
                person_tag=person_tag,
            )
            metadata = {
                "schema": 1,
                "record_type": "handoff",
                "handoff_key": key,
                "kind": kind.value,
                "ownership": ownership.value,
                "state": state.value,
                "created_at": now,
                "updated_at": now,
                "next_check": next_check,
                "revisit_on": revisit_on,
                "revisit_trigger": revisit_trigger.strip() if revisit_trigger else None,
                "person_tag": person_tag,
                "project_id": resolved_project_id,
            }
            notes = build_notes(
                metadata,
                need_from_nick=need,
                agent_after=agent_after,
                done_when=done,
                sources=normalized_sources,
                recheck=recheck,
                additional_notes=additional_notes,
            )
            self.gateway.add_todo(
                {
                    "title": full_title,
                    "notes": notes,
                    "when": scheduled_when,
                    "deadline": deadline,
                    "tags": tags,
                    "list_id": destination_id,
                    "heading_id": heading_id,
                }
            )
            expected_fields = {
                "type": "to-do",
                "title": full_title,
                "notes": notes,
                "status": "incomplete",
                "tags": tags,
                "deadline": deadline,
            }
            expected_fields.update(self._expected_when_fields(scheduled_when))
            if heading_id:
                expected_fields["heading"] = heading_id
            elif resolved_project_id:
                expected_fields["project"] = resolved_project_id
            elif destination_id:
                expected_fields["area"] = destination_id
            created = self._wait_for(
                lambda: self._handoff_with_fields(key, metadata, expected_fields)
            )
            if created is None:
                raise VerificationError(
                    "Things accepted the open request, but the handoff could not be read "
                    "back; do not retry automatically"
                )
            return self._receipt("created", created)

    def resume_handoff(
        self, *, handoff_key: str | None = None, task_id: str | None = None
    ) -> dict[str, Any]:
        task = self._resolve_handoff(handoff_key=handoff_key, task_id=task_id)
        parsed = parse_notes(task.get("notes"))
        assert parsed is not None
        return {
            "status": "found",
            "item": self._public_task(task),
            "metadata": parsed.metadata,
            "packet": parsed.body,
            "deep_link": deep_link(task["uuid"]),
            "expected_modified": task.get("modified"),
        }

    def transition_handoff(
        self,
        *,
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
    ) -> dict[str, Any]:
        if state not in set(HandoffState):
            raise ValidationError(f"unsupported handoff state: {state}")
        when = validate_when(when)
        next_check = validate_date("next_check", next_check)
        revisit_on = validate_date("revisit_on", revisit_on)

        with exclusive_write_lock(self.lock_path):
            task = self._resolve_handoff(handoff_key=handoff_key, task_id=task_id)
            if expected_modified is not None and task.get("modified") != expected_modified:
                raise ConflictError(
                    "the Things item changed after it was read; resume it again before updating"
                )
            parsed = parse_notes(task.get("notes"))
            assert parsed is not None

            metadata = dict(parsed.metadata)
            prior_person_tag = metadata.get("person_tag")
            state_tags = {"waiting", "deferred"}
            if prior_person_tag:
                state_tags.add(prior_person_tag)
            tags = [tag for tag in task.get("tags", []) if tag not in state_tags]
            changes: dict[str, Any] = {}
            new_kind = HandoffKind(metadata["kind"])

            if state is HandoffState.WAITING:
                if not next_check:
                    raise ValidationError("waiting requires a next_check date")
                tags.append(self._require_tag("waiting"))
                if person_tag:
                    tags.append(self._require_tag(person_tag))
                changes["when"] = next_check
                metadata.update(
                    next_check=next_check,
                    revisit_on=None,
                    revisit_trigger=None,
                    person_tag=person_tag,
                )
                if new_kind is HandoffKind.MESSAGE:
                    new_kind = HandoffKind.FOLLOW_UP
                    base_title = task["title"].split(":", 1)[-1].strip()
                    changes["title"] = prefixed_title(new_kind, base_title)
            elif state is HandoffState.DEFERRED:
                if not revisit_on and not revisit_trigger:
                    raise ValidationError("deferred requires revisit_on or revisit_trigger")
                tags.append(self._require_tag("deferred"))
                changes["when"] = revisit_on or "someday"
                metadata.update(
                    next_check=None,
                    revisit_on=revisit_on,
                    revisit_trigger=revisit_trigger.strip() if revisit_trigger else None,
                    person_tag=person_tag,
                )
                if person_tag:
                    tags.append(self._require_tag(person_tag))
            elif state is HandoffState.READY:
                changes["when"] = when or "anytime"
                metadata.update(
                    next_check=None,
                    revisit_on=None,
                    revisit_trigger=None,
                    person_tag=person_tag,
                )
                if person_tag:
                    tags.append(self._require_tag(person_tag))
            else:
                if not outcome or not completion_evidence:
                    raise ValidationError(
                        "complete requires outcome and completion_evidence from the durable system"
                    )
                changes["completed"] = True
                metadata.update(
                    next_check=None,
                    revisit_on=None,
                    revisit_trigger=None,
                    person_tag=person_tag,
                )

            metadata["kind"] = new_kind.value
            metadata["state"] = state.value
            metadata["updated_at"] = self._next_timestamp(metadata.get("updated_at"))
            updated_notes = replace_metadata(task["notes"], metadata)
            if state is HandoffState.COMPLETE:
                updated_notes = append_outcome(
                    updated_notes, outcome or "", completion_evidence or ""
                )
            changes["notes"] = updated_notes
            changes["tags"] = list(dict.fromkeys(tags))

            self.gateway.update_todo(task["uuid"], changes)
            expected_fields = {
                "notes": updated_notes,
                "tags": changes["tags"],
            }
            if "title" in changes:
                expected_fields["title"] = changes["title"]
            if "when" in changes:
                expected_fields.update(self._expected_when_fields(changes["when"]))
            if changes.get("completed") is True:
                expected_fields["status"] = "completed"
            updated = self._wait_for(
                lambda: self._task_with_fields(task["uuid"], metadata, expected_fields)
            )
            if updated is None:
                raise VerificationError(
                    "Things accepted the update request, but the transition could not be "
                    "read back; do not retry automatically"
                )
            return self._receipt("updated", updated)

    def review_handoffs(
        self, *, project_id: str | None = None, as_of: str | None = None
    ) -> dict[str, Any]:
        try:
            review_date = date.fromisoformat(as_of) if as_of else self.clock().astimezone().date()
        except ValueError as exc:
            raise ValidationError("as_of must use YYYY-MM-DD") from exc
        groups: dict[str, list[dict[str, Any]]] = {
            "decisions": [],
            "messages": [],
            "reviews_and_approvals": [],
            "problems_to_unblock": [],
            "joint_follow_through": [],
            "waiting_due": [],
            "waiting_later": [],
            "deferred_due": [],
            "deferred_parked": [],
        }
        for task in self.gateway.list_tasks():
            parsed = parse_notes(task.get("notes"))
            if parsed is None or parsed.metadata.get("record_type") != "handoff":
                continue
            metadata = parsed.metadata
            if project_id and metadata.get("project_id") != project_id:
                continue
            state = HandoffState(metadata["state"])
            public = self._public_task(task)
            public["metadata"] = metadata
            if state is HandoffState.WAITING:
                target = (
                    "waiting_due"
                    if self._on_or_before(metadata.get("next_check"), review_date)
                    else "waiting_later"
                )
            elif state is HandoffState.DEFERRED:
                target = (
                    "deferred_due"
                    if self._on_or_before(metadata.get("revisit_on"), review_date)
                    else "deferred_parked"
                )
            else:
                target = self._ready_group(HandoffKind(metadata["kind"]))
            groups[target].append(public)
        return {
            "as_of": review_date.isoformat(),
            "counts": {name: len(items) for name, items in groups.items()},
            "groups": groups,
        }

    def build_workstream_project(
        self,
        *,
        workstream_key: str,
        title: str,
        purpose: str,
        closure_condition: str,
        authoritative_sources: list[str],
        area_id: str | None = None,
        area_title: str | None = None,
        when: str = "anytime",
    ) -> dict[str, Any]:
        key = validate_handoff_key(workstream_key)
        title = validate_nonempty("title", title, maximum=500)
        purpose = validate_nonempty("purpose", purpose)
        closure_condition = validate_nonempty("closure_condition", closure_condition)
        sources = self._normalize_sources(authoritative_sources)
        when = validate_when(when) or "anytime"

        with exclusive_write_lock(self.lock_path):
            existing = self._find_workstream(key)
            if existing:
                return self._project_receipt("existing", existing)
            resolved_area_id = self._resolve_area(area_id=area_id, area_title=area_title)
            now = self._timestamp()
            metadata = {
                "schema": 1,
                "record_type": "workstream",
                "workstream_key": key,
                "created_at": now,
                "updated_at": now,
            }
            notes = "\n".join(
                [
                    START_MARKER,
                    render_metadata(metadata),
                    END_MARKER,
                    "",
                    "Purpose:",
                    purpose,
                    "",
                    "Authoritative sources:",
                    *(f"- {source}" for source in sources),
                    "",
                    "Closure condition:",
                    closure_condition,
                ]
            )
            if len(notes) > MAX_NOTES_LENGTH:
                raise ValidationError("project notes exceed the Things 10,000-character limit")
            payload = [
                {
                    "type": "project",
                    "attributes": {
                        "title": title,
                        "notes": notes,
                        "when": when,
                        "area-id": resolved_area_id,
                        "items": [
                            {"type": "heading", "attributes": {"title": heading}}
                            for heading in WORKSTREAM_HEADINGS
                        ],
                    },
                }
            ]
            self.gateway.create_json(payload)
            expected_fields = {
                "type": "project",
                "title": title,
                "notes": notes,
                "status": "incomplete",
                "area": resolved_area_id,
            }
            expected_fields.update(self._expected_when_fields(when))
            created = self._wait_for(
                lambda: self._workstream_with_fields(
                    key, metadata, expected_fields, list(WORKSTREAM_HEADINGS)
                )
            )
            if created is None:
                raise VerificationError(
                    "Things accepted the project request, but the workstream could not be "
                    "read back; do not retry automatically"
                )
            return self._project_receipt("created", created)

    def _capture_state(
        self,
        *,
        state: HandoffState,
        ownership: Ownership,
        when: str | None,
        next_check: str | None,
        revisit_on: str | None,
        revisit_trigger: str | None,
        person_tag: str | None,
    ) -> tuple[list[str], str | None]:
        if state is HandoffState.COMPLETE:
            raise ValidationError("capture_handoff cannot create an already completed handoff")
        tags: list[str] = []
        ownership_tag = "solo" if ownership is Ownership.NICK else "build"
        if self._tag_exists(ownership_tag):
            tags.append(self._canonical_tag(ownership_tag))
        if person_tag:
            tags.append(self._require_tag(person_tag))
        if state is HandoffState.WAITING:
            if not next_check:
                raise ValidationError("waiting requires a next_check date")
            tags.append(self._require_tag("waiting"))
            return list(dict.fromkeys(tags)), next_check
        if state is HandoffState.DEFERRED:
            if not revisit_on and not revisit_trigger:
                raise ValidationError("deferred requires revisit_on or revisit_trigger")
            tags.append(self._require_tag("deferred"))
            return list(dict.fromkeys(tags)), revisit_on or "someday"
        return list(dict.fromkeys(tags)), when

    def _resolve_destination(
        self,
        *,
        project_id: str | None,
        project_title: str | None,
        area_id: str | None,
        area_title: str | None,
    ) -> tuple[str | None, str | None]:
        supplied = sum(bool(value) for value in (project_id, project_title, area_id, area_title))
        if supplied > 1:
            raise ValidationError("provide exactly one project or area destination")
        if project_id or project_title:
            project = self._resolve_named_item(
                self.gateway.list_projects(), project_id, project_title, "project"
            )
            return project["uuid"], project["uuid"]
        if area_id or area_title:
            area = self._resolve_named_item(self.gateway.list_areas(), area_id, area_title, "area")
            return area["uuid"], None
        return None, None

    def _resolve_area(self, *, area_id: str | None, area_title: str | None) -> str | None:
        if area_id and area_title:
            raise ValidationError("provide area_id or area_title, not both")
        if not area_id and not area_title:
            return None
        return self._resolve_named_item(
            self.gateway.list_areas(), area_id, area_title, "area"
        )["uuid"]

    @staticmethod
    def _resolve_named_item(
        items: list[dict[str, Any]], item_id: str | None, title: str | None, label: str
    ) -> dict[str, Any]:
        if item_id:
            matches = [item for item in items if item.get("uuid") == item_id]
        else:
            matches = [
                item
                for item in items
                if item.get("title", "").casefold() == (title or "").casefold()
            ]
        if len(matches) != 1:
            raise ValidationError(f"could not resolve exactly one existing Things {label}")
        return matches[0]

    def _resolve_heading(self, project_id: str | None, heading_title: str) -> str | None:
        if not project_id:
            return None
        matches = [
            item
            for item in self.gateway.list_headings(project_id)
            if item.get("title", "").casefold() == heading_title.casefold()
        ]
        return matches[0]["uuid"] if len(matches) == 1 else None

    def _find_handoff(self, key: str) -> dict[str, Any] | None:
        matches = []
        for task in self.gateway.search_tasks(key):
            parsed = parse_notes(task.get("notes"))
            if parsed and parsed.metadata.get("handoff_key") == key:
                matches.append(task)
        if len(matches) > 1:
            raise ConflictError(f"more than one Things task uses handoff key {key}")
        return matches[0] if matches else None

    def _find_workstream(self, key: str) -> dict[str, Any] | None:
        matches = []
        for project in self.gateway.list_projects():
            parsed = parse_notes(project.get("notes"))
            if parsed and parsed.metadata.get("workstream_key") == key:
                matches.append(project)
        if len(matches) > 1:
            raise ConflictError(f"more than one Things project uses workstream key {key}")
        return matches[0] if matches else None

    def _resolve_handoff(
        self, *, handoff_key: str | None, task_id: str | None
    ) -> dict[str, Any]:
        if bool(handoff_key) == bool(task_id):
            raise ValidationError("provide exactly one of handoff_key or task_id")
        task = (
            self._find_handoff(validate_handoff_key(handoff_key or ""))
            if handoff_key
            else self.gateway.get_task(task_id or "")
        )
        if task is None:
            raise ValidationError("managed handoff was not found")
        parsed = parse_notes(task.get("notes"))
        if parsed is None or parsed.metadata.get("record_type") != "handoff":
            raise ConflictError("task is not managed by things-agent-workflow")
        return task

    def _handoff_with_fields(
        self,
        key: str,
        expected_metadata: dict[str, Any],
        expected_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        task = self._find_handoff(key)
        return self._managed_item_with_fields(task, expected_metadata, expected_fields)

    def _task_with_fields(
        self,
        task_id: str,
        expected_metadata: dict[str, Any],
        expected_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        task = self.gateway.get_task(task_id)
        return self._managed_item_with_fields(task, expected_metadata, expected_fields)

    def _workstream_with_fields(
        self,
        key: str,
        expected_metadata: dict[str, Any],
        expected_fields: dict[str, Any],
        expected_headings: list[str],
    ) -> dict[str, Any] | None:
        project = self._find_workstream(key)
        matched = self._managed_item_with_fields(project, expected_metadata, expected_fields)
        if matched is None:
            return None
        headings = [
            item.get("title")
            for item in project.get("items", [])
            if item.get("type") == "heading"
        ]
        return project if headings == expected_headings else None

    @classmethod
    def _managed_item_with_fields(
        cls,
        item: dict[str, Any] | None,
        expected_metadata: dict[str, Any],
        expected_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        if item is None:
            return None
        parsed = parse_notes(item.get("notes"))
        if parsed is None or parsed.metadata != expected_metadata:
            return None
        return item if cls._fields_match(item, expected_fields) else None

    @staticmethod
    def _fields_match(item: dict[str, Any], expected_fields: dict[str, Any]) -> bool:
        for key, expected in expected_fields.items():
            actual = item.get(key)
            if key == "tags":
                if sorted(actual or []) != sorted(expected or []):
                    return False
            elif actual != expected:
                return False
        return True

    def _expected_when_fields(self, when: str | None) -> dict[str, Any]:
        if when is None:
            return {}
        if when == "someday":
            return {"start": "Someday", "start_date": None, "reminder_time": None}
        if when == "anytime":
            return {"start": "Anytime", "start_date": None, "reminder_time": None}
        today = self.clock().astimezone().date()
        if when == "tomorrow":
            start_date = today + timedelta(days=1)
        elif when in {"today", "evening"}:
            start_date = today
        else:
            start_date = date.fromisoformat(when.split("@", 1)[0])
        _, separator, reminder_time = when.partition("@")
        return {
            "start": "Anytime",
            "start_date": start_date.isoformat(),
            "reminder_time": reminder_time if separator else None,
        }

    def _wait_for(self, lookup: Callable[[], dict[str, Any] | None]) -> dict[str, Any] | None:
        deadline = time.monotonic() + self.verification_timeout
        while True:
            value = lookup()
            if value is not None:
                return value
            if time.monotonic() >= deadline:
                return None
            self.sleeper(0.1)

    def _canonical_tag(self, tag: str) -> str:
        matches = [
            item["title"]
            for item in self.gateway.list_tags()
            if item.get("title", "").casefold() == tag.casefold()
        ]
        if len(matches) != 1:
            raise ValidationError(f"could not resolve exactly one existing Things tag: {tag}")
        return matches[0]

    def _tag_exists(self, tag: str) -> bool:
        return any(
            item.get("title", "").casefold() == tag.casefold()
            for item in self.gateway.list_tags()
        )

    def _require_tag(self, tag: str) -> str:
        return self._canonical_tag(validate_nonempty("tag", tag, maximum=200))

    @staticmethod
    def _normalize_sources(sources: list[str]) -> list[str]:
        return [validate_nonempty("source", source, maximum=1_000) for source in sources]

    def _timestamp(self) -> str:
        return self.clock().astimezone(UTC).isoformat()

    def _next_timestamp(self, previous: str | None) -> str:
        candidate = self.clock().astimezone(UTC)
        if previous:
            previous_time = datetime.fromisoformat(previous).astimezone(UTC)
            if candidate <= previous_time:
                candidate = previous_time + timedelta(microseconds=1)
        return candidate.isoformat()

    @staticmethod
    def _on_or_before(value: str | None, comparison: date) -> bool:
        return bool(value and date.fromisoformat(value) <= comparison)

    @staticmethod
    def _ready_group(kind: HandoffKind) -> str:
        if kind is HandoffKind.DECISION:
            return "decisions"
        if kind in {HandoffKind.MESSAGE, HandoffKind.FOLLOW_UP}:
            return "messages"
        if kind in {HandoffKind.REVIEW, HandoffKind.APPROVAL}:
            return "reviews_and_approvals"
        if kind is HandoffKind.UNBLOCK:
            return "problems_to_unblock"
        return "joint_follow_through"

    @staticmethod
    def _public_task(task: dict[str, Any]) -> dict[str, Any]:
        return {
            key: task.get(key)
            for key in (
                "uuid",
                "title",
                "status",
                "project",
                "project_title",
                "area",
                "area_title",
                "heading",
                "heading_title",
                "start",
                "start_date",
                "reminder_time",
                "deadline",
                "tags",
                "modified",
            )
        }

    def _receipt(self, status: str, task: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_notes(task.get("notes"))
        return {
            "status": status,
            "verified": True,
            "item": self._public_task(task),
            "metadata": parsed.metadata if parsed else None,
            "deep_link": deep_link(task["uuid"]),
        }

    @staticmethod
    def _project_receipt(status: str, project: dict[str, Any]) -> dict[str, Any]:
        items = project.get("items", [])
        return {
            "status": status,
            "verified": True,
            "project": {
                "uuid": project.get("uuid"),
                "title": project.get("title"),
                "area": project.get("area"),
                "area_title": project.get("area_title"),
                "headings": [item.get("title") for item in items if item.get("type") == "heading"],
            },
            "deep_link": deep_link(project["uuid"]),
        }
