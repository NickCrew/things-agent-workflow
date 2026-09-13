# Architecture

## Operating model

Things Agent Workflow is a personal control plane for the human obligations created by agent
work. It does not mirror Jira, track agent-only implementation, or preserve delivery evidence.

A handoff enters Things only when the agent cannot safely continue without a decision,
message, approval, review, access change, publication, or other action from Nick. A joint
handoff may include the agent work that follows Nick's action, but it must never become a
general agent backlog.

## Lifecycle

Managed handoffs use four states:

| State | Meaning | Things representation |
| --- | --- | --- |
| `ready` | Nick can act now or on a scheduled date. | Inbox, Anytime, Today, or an upcoming date |
| `waiting` | An ask has gone out and Nick owns the follow-up. | `waiting`, optional person tag, and a required next-check date |
| `deferred` | Nick intentionally parked the obligation. | `deferred`, Someday or a revisit date, and a required return trigger |
| `complete` | The human-agent loop closed and its durable outcome was recorded. | Completed to-do with outcome and evidence in its notes |

`waiting` and `deferred` suppress routine agent reminders. An agent may surface them again
when the next-check date arrives, the return trigger becomes true, new evidence changes the
decision, or the user asks for a review.

## Managed notes

Each handoff begins with a versioned JSON record between plain-text markers. The remainder is
a human-readable packet.

```text
[things-agent-workflow]
{"schema":1,"handoff_key":"crm-mapping:CRM-12345:owner-review",...}
[/things-agent-workflow]

Need from Nick:
Approve, replace, or reject the proposed intent.

Agent after:
Record the choice, regenerate the projection, and run the bounded checks.

Done when:
The decision is present in the authoritative plan and the projection is verified.

Sources:
- ~/source/crm-mapping/docs/plans/example.md
- CRM-12345
```

The stable `handoff_key` is the idempotency key across sessions. Agents search for the exact
managed key before creating a task.

## Workstream projects

A durable workstream project uses these headings:

1. Decisions
2. Messages and asks
3. Reviews and approvals
4. Problems to unblock
5. Joint follow-through

Dates and tags represent state. Headings represent the kind of intervention, so the project
does not need to be reorganized each time a task moves from ready to waiting.

The builder creates the project and headings together, then initial handoffs are captured
individually. Things returns IDs for top-level JSON objects but not for to-dos nested inside a
project. Separate capture preserves an independently verified ID and stable key for every
handoff.

## Write contract

Every write follows the same boundary:

1. Validate ownership, state, dates, tags, and destination.
2. Acquire the process-shared file lock.
3. Search again for the stable key while holding the lock.
4. Construct the Things URL without logging secrets.
5. Open the URL once.
6. Poll the read-only Things database for the exact managed record and requested fields.
7. Return the item ID, deep link, and fields read from Things.

If verification times out, the server reports that the write was submitted but unconfirmed.
It never retries automatically. The caller must reconcile by key before considering another
write.

Updates require the authorization token that Things stores in its database. The token remains
inside the service process and is never included in tool results or logs.

Things supports `x-callback-url`, but the first release does not depend on a callback handler.
A URL callback does not return through stdio by itself. The server instead serializes writes,
polls the read-only database by stable key, and verifies the stored fields before it reports
success. A later callback receiver could reduce polling latency without changing the tool
contract.

For handoffs, verification compares the type, title, managed notes, status, tags, deadline,
schedule, destination, and heading when one was resolved. Transitions compare every changed
field. Project creation compares the type, title, notes, status, Area, schedule, and exact
heading sequence. Schedule verification includes both the date and reminder time when the
request contains a time.

The Things database represents a to-do under a heading with the heading ID but no direct
project ID. In that case, the pre-resolved heading ID verifies placement, and managed metadata
retains the parent project ID for review filtering and session handoff.

An `existing` receipt has different semantics. It proves that one managed item already uses
the stable key; it does not compare that item with the new request or update it.

## Concurrency

Every MCP client can start its own service process. A file lock serializes the duplicate check
and write across those processes. The managed key prevents a second agent from creating the
same handoff after the first write becomes visible.

Transitions also accept the item's expected modification timestamp. A mismatch stops the
write so one agent cannot silently overwrite a newer human or agent update.
