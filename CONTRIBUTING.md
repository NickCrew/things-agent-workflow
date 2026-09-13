# Contributing

Changes to this repository can affect durable personal tasks. Keep the implementation small,
make every write explicit, and prove behavior without using the live Things database as a test
fixture.

## Invariants

Every change must preserve these boundaries:

- Things contains Nick-only or Nick-plus-agent obligations, never an agent-only backlog.
- Jira remains the team delivery system.
- A stable key identifies one managed handoff or workstream across sessions.
- Every write is serialized, submitted once, and read back before success is reported.
- An ambiguous write is never retried automatically.
- Updates reject stale `expected_modified` values when the caller supplies one.
- The Things authorization token never appears in tool output, logs, command arguments, or
  repository files.
- Tests never open a live Things URL.

Read [Architecture](docs/architecture.md) and [Tool reference](docs/tool-reference.md) before
changing lifecycle, metadata, or write behavior.

## Set up the development environment

```sh
git clone git@github.com:NickCrew/things-agent-workflow.git
cd things-agent-workflow
uv sync --frozen
```

The supported runtime is Python 3.12 or later on macOS.

## Run the checks

```sh
uv run pytest --cov=things_agent_workflow --cov-report=term-missing
uv run ruff check .
uv build
```

The repository enforces at least 90 percent branch-aware coverage. The current suite uses
`FakeThingsGateway`, which preserves Things-shaped data and write side effects without opening
the application.

Inspect the MCP schema and perform the read-only live check separately:

```sh
uv run fastmcp list \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --json

uv run fastmcp call \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --target workflow_status \
  --json
```

The second command reads the local Things database. Neither command writes to Things.

## Test changes at the right boundary

For a write-path change:

1. Add a failing service test that reproduces the missing behavior.
2. Keep the fake gateway structurally consistent with fields returned by `things-py`.
3. Implement the smallest production change that passes the test.
4. Cover submission failure, incomplete readback, duplicate identity, and conflict behavior when
   the change touches those paths.
5. Run the full suite, not only the new test.

Do not add production methods used only by tests. Mock the application launch boundary, not the
service behavior being asserted.

A live write is not a smoke test. Perform one only when the user explicitly authorizes that
specific Things mutation, then report the exact item and readback result.

## Keep documentation coupled to behavior

Update documentation in the same change when modifying:

| Change | Required documentation |
| --- | --- |
| Tool name, parameter, enum, result, or validation | `docs/tool-reference.md` and affected skill |
| User workflow or admission rule | `docs/workflows.md` and affected skill |
| MCP configuration or prerequisite | `docs/getting-started.md` |
| Environment variable, timeout, failure, or recovery path | `docs/operations.md` |
| Lifecycle, metadata, verification, or concurrency | `docs/architecture.md` |
| Released behavior | `CHANGELOG.md` and package version |

Commands in documentation must be run before the change is committed. Use placeholders only
when a value genuinely differs by installation, and label them clearly.

## Add or change an MCP tool

When adding a tool:

1. Put domain behavior in `ThingsWorkflowService` and keep the MCP wrapper thin.
2. Add or extend the gateway protocol only for a real Things boundary.
3. Define the typed FastMCP signature and a concise behavioral docstring.
4. Add service tests and an MCP integration assertion for the exposed schema.
5. Document parameters, conditional requirements, results, errors, and an example.
6. Update the relevant user-invoked skill without making writes implicit.

## Review and commit

Documentation-only changes are local risk. Tool contracts, persistence reads, and state
transitions are behavioral risk. Authorization, durable writes, and verification semantics are
controlled risk and require the full suite plus a focused success-path and failure-path review.

Before committing:

```sh
git diff --check
git status --short
```

Inspect the exact staged diff. Use a short, imperative Conventional Commit subject, and keep
unrelated changes out of the commit.
