# Changelog

This file records user-visible changes to Things Agent Workflow.

## Unreleased

### Added

- Getting-started, tool-reference, workflow, operations, and contribution guides.
- Worked examples for each managed handoff lifecycle.
- Troubleshooting and reconciliation procedures for ambiguous writes and conflicts.

### Changed

- Write confirmation now compares requested Things fields, including reminder time, as well as
  managed metadata.
- Ready transitions use the URL scheme's empty-value form to return a scheduled to-do to
  Anytime.
- Heading placement verification follows the parent-project shape returned by `things-py`.
- Project confirmation now requires the exact standard heading sequence.

## 0.1.0 - 2026-09-12

### Added

- Semantic MCP tools for capture, resume, transition, review, and workstream project creation.
- Stable managed keys, process-shared write locking, readback confirmation, and optimistic
  conflict checks.
- `remind-me`, `track-this`, `things-review`, and `things-project` user-invoked skills.
- Side-effect-free unit and MCP integration tests.
