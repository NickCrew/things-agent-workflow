---
name: track-this
description: Capture, resume, defer, transition, or complete the user's side of a human-agent handoff in Things 3. Use only when the user invokes this skill directly.
---

# Track This

Keep a human obligation visible across agent sessions. The invocation authorizes one Things mutation unless the user explicitly requests several separate handoffs.

## Admission test

Ask whether an agent could safely complete the work if the user disappeared.

- If yes, keep it in the agent session, worktree, or repository handoff.
- If it is team scope or shared backlog, use Jira.
- If a decision, message, review, approval, access change, publication, or follow-up requires the user, Things may track that exact intervention.
- A joint item may include the agent work that follows the user's action. It must not become a general agent backlog.

## Capture

Use `capture_handoff` with:

- a deterministic `handoff_key`, preferably `<workstream>:<jira-or-artifact>:<human-action>`;
- the narrowest matching `kind`;
- `ownership=nick` for user-only work or `ownership=nick-agent` when the agent continues afterward;
- one clear `need_from_nick`, `agent_after`, and `done_when` contract;
- durable sources and a `recheck` note for facts that can drift;
- an exact existing project or area when known, otherwise the Inbox.

Waiting means an ask has already gone out and requires `next_check`. Deferred means the user deliberately parked the item and requires `revisit_on` or `revisit_trigger`. Person tags describe who is involved; `waiting` separately records whether the ask has been sent.

After verified capture, stop routinely resurfacing the issue. Surface it again only when its date arrives, its return trigger becomes true, new evidence changes the decision, current work conflicts with it, or the user requests a review.

## Resume or transition

Call `resume_handoff` before acting on a Things link, item ID, or handoff key. Revalidate every drift-prone source before using it as current evidence.

Use `transition_handoff` for one explicit state change:

- `ready`: actionable now or on `when`;
- `waiting`: the message or ask was sent, with a required `next_check`;
- `deferred`: intentionally parked, with a required date or event trigger;
- `complete`: the loop closed, with the outcome and its durable evidence.

Pass `expected_modified` from `resume_handoff` when updating an item. If it conflicts or verification is ambiguous, stop and do not retry.
