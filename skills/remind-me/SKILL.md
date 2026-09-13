---
name: remind-me
description: Create one deliberate Things 3 reminder from an explicit user request. Use only when the user invokes this skill directly.
---

# Remind Me

Create one verified Things task for an action that belongs to the user. The invocation authorizes one Things write.

## Boundaries

- Never capture tasks automatically or scan conversation history for candidates.
- Do not use Things for agent-only work, Jira backlog, delivery evidence, or informational memory.
- Use an existing project or area only when the destination is explicit or unambiguous. Otherwise use the Inbox.
- Never retry an unverified write. A retry can create a duplicate.

## Create the reminder

Use `capture_handoff` from the Things Agent Workflow MCP server.

1. Write a short, action-led title.
2. Set `kind` to `task`.
3. Set `ownership` to `nick`, unless the reminder explicitly includes agent follow-through.
4. Build a stable lowercase `handoff_key` from the strongest durable identifier and action. For example, `crm-mapping:crm-12345:owner-review`. For a personal reminder without an identifier, use stable normalized title terms.
5. Resolve relative dates in the user's local timezone. Use `when` for the next attention date. Use `deadline` only for a real due date. Include a reminder time only when the user supplies one.
6. Put durable URLs, repository paths, and concise context in `sources` or `additional_notes`. Do not store credentials or session-scoped plan paths.
7. Set `need_from_nick` to the requested action and `done_when` to its observable completion condition.
8. Use `state=deferred` only when the user deliberately parks the action, and include `revisit_on` or `revisit_trigger`.

Report the verified title, schedule or Inbox, destination, tags, and returned Things link. If the server returns `existing`, report the existing match instead of creating another.
