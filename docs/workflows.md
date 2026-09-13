# Workflows

Use Things for the human obligations produced by agent work. Jira still owns team delivery
scope, and the active session or repository owns agent-only work.

## Decide whether an item belongs in Things

Ask one question: could an agent safely finish this if Nick disappeared?

| Answer | Put the work in |
| --- | --- |
| Yes | The agent session, worktree, or repository handoff. |
| No, because Nick must decide, send, approve, review, publish, or unlock something | Things. |
| It is shared team scope or backlog | Jira. |

Do not copy an entire Jira issue into Things. Capture the narrow intervention that belongs to
Nick, then link the Jira issue as a source.

## Create a simple reminder

Invoke `$remind-me` when the item is a direct personal action:

```text
$remind-me Review the release notes Monday morning. Put it in Platform Ops.
```

The skill creates one `kind=task`, `ownership=nick` handoff. A useful request includes the
action, real date or timing, and destination when it matters. Vague timing stays unscheduled;
the agent must not invent a date.

Equivalent MCP arguments:

```json
{
  "handoff_key": "platform-ops:review-release-notes",
  "kind": "task",
  "ownership": "nick",
  "title": "Review the release notes",
  "need_from_nick": "Read the candidate release notes and mark corrections.",
  "done_when": "The candidate notes contain the approved corrections.",
  "when": "2026-09-14@09:00",
  "area_title": "Platform Ops"
}
```

## Capture a decision with agent follow-through

Use `$track-this` when Nick's action unlocks more agent work:

```text
$track-this I need to choose the CRM-12345 rollout boundary, then the agent should update the plan and rerun its checks.
```

```json
{
  "handoff_key": "release:crm-12345:rollout-boundary",
  "kind": "decision",
  "ownership": "nick-agent",
  "title": "choose the CRM-12345 rollout boundary",
  "need_from_nick": "Approve, replace, or reject the proposed rollout boundary.",
  "agent_after": "Record the choice, update the plan, and rerun the bounded checks.",
  "done_when": "The decision is recorded in the release plan and the checks pass.",
  "sources": [
    "CRM-12345",
    "~/source/example/docs/release-plan.md"
  ],
  "recheck": "Revalidate the current branch, Jira status, and deployment state before acting.",
  "project_title": "CRM Release Platform"
}
```

After verified capture, the active agent can stop repeating the decision in routine updates.
The next session resumes the managed packet and rechecks anything that may have changed.

## Send a message, then wait

Capture the message while it is still Nick's action:

```json
{
  "handoff_key": "release:crm-12345:send-approval-request",
  "kind": "message",
  "ownership": "nick-agent",
  "title": "approval request for CRM-12345",
  "need_from_nick": "Send the prepared approval request to Damon.",
  "agent_after": "Process the response and update the release decision record.",
  "done_when": "The response is reflected in the authoritative release record.",
  "person_tag": "@damon",
  "project_title": "CRM Release Platform"
}
```

After the message is sent:

1. Call `resume_handoff` and retain `expected_modified`.
2. Call `transition_handoff` with `state=waiting`, a real `next_check`, and the same person tag.
3. Confirm that the title changed from `Send:` to `Follow up:`.

```json
{
  "handoff_key": "release:crm-12345:send-approval-request",
  "state": "waiting",
  "expected_modified": "value-returned-by-resume",
  "next_check": "2026-09-16",
  "person_tag": "@damon"
}
```

The agent should not surface it again before September 16 unless new evidence changes the
decision or current work conflicts with it.

## Defer an issue

Use a date when the issue should return on a known day:

```json
{
  "handoff_key": "tooling:choose-index-migration",
  "state": "deferred",
  "expected_modified": "value-returned-by-resume",
  "revisit_on": "2026-10-01"
}
```

Use a trigger when the return depends on an event:

```json
{
  "handoff_key": "tooling:choose-index-migration",
  "state": "deferred",
  "expected_modified": "value-returned-by-resume",
  "revisit_trigger": "The replacement index reaches production"
}
```

Event-triggered deferral places the task in Someday. It remains in `deferred_parked` until a
weekly or context-aware review asks whether the trigger occurred.

## Resume and complete a handoff

Resume first, then verify every drift-prone source named in the packet. A Things note is
re-entry context, not proof that Jira, Git, deployment, or runtime state still matches it.

Complete only after the outcome exists in a durable system:

```json
{
  "handoff_key": "release:crm-12345:rollout-boundary",
  "state": "complete",
  "expected_modified": "value-returned-by-resume",
  "outcome": "Use the application-version boundary for the first rollout.",
  "completion_evidence": "~/source/example/docs/release-plan.md at commit 1234abc"
}
```

The service appends the outcome and evidence to the Things notes, removes workflow state and
person tags, and completes the to-do. It does not treat Things as the authoritative decision
record.

## Build a workstream project

Invoke `$things-project` when several human obligations share a durable workstream and will
survive more than one agent session:

```text
$things-project Build a CRM Release Platform workstream in the Release Train Area. Track only decisions, messages, approvals, unblocks, and joint follow-through.
```

```json
{
  "workstream_key": "release:crm-release-platform",
  "title": "CRM Release Platform",
  "purpose": "Keep the human control points from parallel release agents visible.",
  "closure_condition": "No open human obligations remain for the release platform workstream.",
  "authoritative_sources": [
    "~/source/crm-release-platform",
    "https://unaverse.atlassian.net/"
  ],
  "area_title": "Release Train",
  "when": "anytime"
}
```

The builder creates the standard headings but no child to-dos. Capture each initial handoff
separately through `$track-this`; nested Things JSON creation does not return the child IDs
needed for independent lifecycle management.

## Review the control plane

Invoke `$things-review` for a read-only briefing. A daily review should show ready queues,
waiting follow-ups that are due, and date-deferred items that are due. It should suppress
future waits and parked deferrals.

During an explicit weekly review, inspect `deferred_parked` and ask whether any event trigger
has become true. Transition only the items Nick selects.

The review is not a Jira status report. Its job is to answer: what does Nick need to decide,
send, approve, review, unblock, or resume next?
