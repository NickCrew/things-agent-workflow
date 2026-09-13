---
name: things-project
description: Build one Things 3 workstream project for human decisions and handoffs across multiple agent sessions. Use only when the user invokes this skill directly.
---

# Things Project

Create a durable Things project when a workstream has several ongoing human obligations or will survive multiple agent sessions. Do not create a project for one reminder, one agent, or one session.

Use `build_workstream_project` once with:

- a stable lowercase `workstream_key`;
- a concise project title;
- the human-control purpose, not a copy of the delivery charter;
- authoritative repository, Jira, or planning sources;
- the condition under which no human obligations remain;
- an existing Area only when its destination is explicit or unambiguous.

The tool creates the standard headings:

- Decisions
- Messages and asks
- Reviews and approvals
- Problems to unblock
- Joint follow-through

The project is not a Jira mirror. Seed it only with tasks that require the user or the user plus an agent. Capture each initial task through `$track-this` so it receives a stable handoff key and verified lifecycle metadata.

Never retry an unverified project write. Return the verified project title, Area, headings, and Things link.
