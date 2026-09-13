# Tool reference

The Things Agent Workflow MCP server exposes six tools. Three mutate Things, three are
read-only.

| Tool | Access |
| --- | --- |
| `capture_handoff` | Creates one to-do. |
| `transition_handoff` | Updates one managed to-do. |
| `build_workstream_project` | Creates one project and its headings. |
| `resume_handoff` | Read-only. |
| `review_handoffs` | Read-only. |
| `workflow_status` | Read-only. |

The skills require explicit user invocation before a write. Calling a mutation tool directly
must follow the same rule.

## Shared values

### Handoff keys

`handoff_key` and `workstream_key` are idempotency keys. They must:

- contain 3 through 200 characters;
- start with a lowercase letter or digit;
- use only lowercase letters, digits, `:`, `.`, `_`, `/`, and `-`.

Prefer `<workstream>:<jira-or-artifact>:<human-action>`, such as
`crm-mapping:crm-12345:owner-review`. A second capture with the same key returns the existing
item and does not apply or compare the new request.

### Kinds and title prefixes

| `kind` | Title prefix | Project heading |
| --- | --- | --- |
| `task` | None | Joint follow-through |
| `decision` | `Decide:` | Decisions |
| `message` | `Send:` | Messages and asks |
| `review` | `Review:` | Reviews and approvals |
| `approval` | `Approve:` | Reviews and approvals |
| `unblock` | `Unblock:` | Problems to unblock |
| `follow-up` | `Follow up:` | Messages and asks |
| `publish` | `Publish:` | Joint follow-through |
| `joint` | `Continue with agent:` | Joint follow-through |

The server does not duplicate a prefix already present in the title. When the destination
project contains exactly one matching standard heading, capture places the handoff under it.
Otherwise it places the handoff at the project root.

### Ownership

| `ownership` | Meaning | Optional tag |
| --- | --- | --- |
| `nick` | Nick owns the action. | `solo` |
| `nick-agent` | Nick acts, then an agent continues. | `build` |

Agent-only ownership is invalid. `nick-agent` requires `agent_after`. Missing `solo` or `build`
tags do not block capture; they only remove the optional ownership marker.

### States

| `state` | Required input | Schedule and tags |
| --- | --- | --- |
| `ready` | None | Uses `when`, or stays unscheduled during capture. |
| `waiting` | `next_check` | Schedules the next-check date and requires the `waiting` tag. |
| `deferred` | `revisit_on` or `revisit_trigger` | Uses the revisit date, or Someday for an event trigger, and requires the `deferred` tag. |
| `complete` | `outcome` and `completion_evidence` during transition | Completes the to-do and records the result. |

`capture_handoff` rejects `state=complete`. Use `transition_handoff` after the human-agent loop
has closed.

### Dates

`deadline`, `next_check`, and `revisit_on` accept `YYYY-MM-DD` only. `as_of` uses the same
format.

`when` accepts:

- `today`
- `tomorrow`
- `evening`
- `anytime`
- `someday`
- `YYYY-MM-DD`
- `YYYY-MM-DD@HH:MM`

The time uses the Mac's local timezone. Readback verifies the scheduled date or Things list,
and verifies the reminder time when the request includes one.

### Destinations and tags

Provide no more than one of `project_id`, `project_title`, `area_id`, or `area_title`. Titles
match case-insensitively and must resolve to exactly one existing item. With no destination,
Things chooses the Inbox or its default placement.

`person_tag` must already exist. The server fails before writing when a required state tag or
person tag cannot be resolved exactly once.

## `capture_handoff`

Creates one managed to-do or returns the item already using its key.

### Parameters

| Parameter | Required | Meaning |
| --- | --- | --- |
| `handoff_key` | Yes | Stable idempotency key. |
| `kind` | Yes | One of the nine handoff kinds. |
| `ownership` | Yes | `nick` or `nick-agent`. |
| `title` | Yes | Action title, at most 500 characters before prefixing. |
| `need_from_nick` | Yes | The exact human action, at most 4,000 characters. |
| `done_when` | Yes | Observable closure condition, at most 4,000 characters. |
| `agent_after` | For `nick-agent` | What the agent does after Nick acts. |
| `sources` | No | Durable URLs, issue keys, or paths, each at most 1,000 characters. |
| `recheck` | No | Facts the next agent must verify again. |
| `additional_notes` | No | Context that does not fit another field. |
| `state` | No | Defaults to `ready`; `complete` is invalid during capture. |
| `when` | No | Ready-state attention date, list, or date-time. |
| `deadline` | No | Real due date, not a reminder date. |
| `next_check` | For `waiting` | Follow-up date. |
| `revisit_on` | Conditional | Deferred revisit date. |
| `revisit_trigger` | Conditional | Deferred event that makes the item relevant again. |
| `person_tag` | No | Existing Things tag for the person involved. |
| `project_id` | No | Exact project destination by ID. |
| `project_title` | No | Exact project destination by title. |
| `area_id` | No | Exact Area destination by ID. |
| `area_title` | No | Exact Area destination by title. |

The managed note can contain at most 10,000 characters after metadata and headings are added.

### Result

`status` is `created` or `existing`. A created receipt has passed field readback. An existing
receipt proves only that one managed item already owns the key.

```json
{
  "status": "created",
  "verified": true,
  "item": {
    "uuid": "things-item-id",
    "title": "Decide: choose the rollout boundary",
    "status": "incomplete",
    "project": null,
    "project_title": null,
    "area": null,
    "area_title": null,
    "heading": "things-heading-id",
    "heading_title": "Decisions",
    "start": "Anytime",
    "start_date": null,
    "reminder_time": null,
    "deadline": null,
    "tags": ["build"],
    "modified": "database-modification-value"
  },
  "metadata": {
    "schema": 1,
    "record_type": "handoff",
    "handoff_key": "release:crm-12345:rollout-boundary",
    "kind": "decision",
    "ownership": "nick-agent",
    "state": "ready",
    "created_at": "2026-09-12T20:00:00+00:00",
    "updated_at": "2026-09-12T20:00:00+00:00",
    "next_check": null,
    "revisit_on": null,
    "revisit_trigger": null,
    "person_tag": null,
    "project_id": "things-project-id"
  },
  "deep_link": "things:///show?id=things-item-id"
}
```

## `resume_handoff`

Returns the current managed packet. Provide exactly one identity.

### Parameters

| Parameter | Required | Meaning |
| --- | --- | --- |
| `handoff_key` | One of two | Stable managed key. |
| `task_id` | One of two | Things to-do ID. |

### Result

The result contains `status: found`, the public item fields, parsed metadata, the human-readable
`packet`, a Things deep link, and `expected_modified`. Pass `expected_modified` to the next
transition so a newer human or agent edit cannot be overwritten silently.

## `transition_handoff`

Changes the state of one managed to-do. It does not move the item to another project or Area.

### Parameters

| Parameter | Required | Meaning |
| --- | --- | --- |
| `state` | Yes | `ready`, `waiting`, `deferred`, or `complete`. |
| `handoff_key` | One identity | Stable managed key. |
| `task_id` | One identity | Things to-do ID. |
| `expected_modified` | Recommended | Value returned by `resume_handoff`. |
| `when` | For scheduled `ready` | New attention date or list. Defaults to Anytime. |
| `next_check` | For `waiting` | Required follow-up date. |
| `revisit_on` | Conditional | Deferred revisit date. |
| `revisit_trigger` | Conditional | Deferred event trigger. |
| `person_tag` | No | Existing person tag to retain in the new state. |
| `outcome` | For `complete` | Human-readable result. |
| `completion_evidence` | For `complete` | Durable location where the result was recorded. |

Moving to `waiting`, `deferred`, or `ready` removes the prior state tag and prior person tag.
The requested state's tags are then applied. Moving a `message` to `waiting` changes its kind
to `follow-up` and rewrites `Send:` as `Follow up:`.

Completion appends `Outcome` and `Completion evidence` sections to the notes. It does not clear
an existing deadline or schedule.

### Result

The result has the same receipt shape as capture, with `status: updated`.

## `review_handoffs`

Groups incomplete managed handoffs without changing Things.

### Parameters

| Parameter | Required | Meaning |
| --- | --- | --- |
| `project_id` | No | Limit the review to metadata linked to one project ID. |
| `as_of` | No | Review date in `YYYY-MM-DD`; defaults to the Mac's local date. |

### Result

The result contains `as_of`, a count for each group, and the grouped public items with metadata.

| Group | Contents |
| --- | --- |
| `decisions` | Ready decisions. |
| `messages` | Ready messages and follow-ups. |
| `reviews_and_approvals` | Ready reviews and approvals. |
| `problems_to_unblock` | Ready unblock items. |
| `joint_follow_through` | Ready tasks, publications, and joint work. |
| `waiting_due` | Waiting items whose next-check date is on or before `as_of`. |
| `waiting_later` | Waiting items with a later next-check date. |
| `deferred_due` | Deferred items whose revisit date is on or before `as_of`. |
| `deferred_parked` | Later or event-triggered deferred items. |

Completed and unmanaged Things items are excluded.

## `build_workstream_project`

Creates a managed project with the five standard headings. It does not create child handoffs;
capture those separately so each one receives its own ID and stable key.

### Parameters

| Parameter | Required | Meaning |
| --- | --- | --- |
| `workstream_key` | Yes | Stable project idempotency key. |
| `title` | Yes | Project title, at most 500 characters. |
| `purpose` | Yes | Why this human-control workstream exists. |
| `closure_condition` | Yes | Condition under which no human obligations remain. |
| `authoritative_sources` | Yes | Durable repository, Jira, or planning sources. |
| `area_id` | No | Existing Area ID. |
| `area_title` | No | Existing Area title; do not combine with `area_id`. |
| `when` | No | Project start value; defaults to `anytime`. |

### Result

The result uses `status: created` or `status: existing`, `verified: true`, the project ID,
title, Area, heading titles, and a Things deep link. As with handoffs, `existing` does not
compare the old project with the new request.

## `workflow_status`

Checks local Things database access and reports:

### Result

- `read_access`;
- visible Area and project counts;
- presence of the `waiting` and `deferred` tags;
- presence of the optional `solo` and `build` tags.

It does not return titles, task contents, notes, or IDs.

## Errors and confirmation

| Error | Meaning | Caller action |
| --- | --- | --- |
| Validation error | Input, destination, date, tag, or state contract is invalid. | Correct the request before trying again. |
| Conflict error | A stable key is duplicated, notes are malformed, or `expected_modified` is stale. | Resume or inspect the item; do not overwrite it. |
| Verification error | Things was opened once, but the exact requested fields did not appear before timeout. | Reconcile by key or ID; never retry automatically. |
| MCP or process error | The Things database cannot be read or macOS cannot open the URL. | Fix the local runtime before another write attempt. |

For new handoffs, readback checks the type, title, full notes, status, tags, deadline, supported
schedule fields, destination, and resolved heading. Transitions check the new notes, tags,
title when changed, schedule when changed, and completion status. Project creation checks the
type, title, full notes, status, Area, schedule, and exact heading sequence.

For a to-do assigned to a heading, the read database exposes the heading ID but not a direct
project ID. The verified heading proves placement because it was resolved within the requested
project, while `metadata.project_id` retains the parent project identity.
