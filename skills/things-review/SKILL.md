---
name: things-review
description: Review the user's managed human-agent obligations in Things 3 without changing them. Use only when the user invokes this skill directly.
---

# Things Review

Give the user a decision-oriented briefing of their side of parallel agent work. This workflow is read-only unless the user separately requests a transition.

Use `review_handoffs`. Limit the query to the current Things project when the workstream mapping is unambiguous; otherwise review all managed handoffs.

Present only useful queues:

1. Decisions needed.
2. Messages ready to send.
3. Reviews and approvals.
4. Problems only the user can unblock.
5. Joint work that can resume after user input.
6. Waiting follow-ups whose next-check date has arrived.
7. Deferred items whose revisit date has arrived.

Do not turn the result into a Jira status report. Do not surface future waiting items or parked deferred items during a daily review. During an explicit weekly review, include event-triggered deferred items and ask whether their trigger has occurred.

Treat Things notes as re-entry context, not current operational proof. Before recommending action, revalidate referenced branches, Jira issues, merge requests, deployments, approvals, or runtime state when they could have changed.
