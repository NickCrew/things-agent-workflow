# Operations

The service is deliberately local. It reads the Things database through `things-py`, sends
writes through the documented Things URL scheme, and relies on Things itself to persist and
sync data.

## Runtime modes

Use stdio for Codex and Claude. It is the default and keeps the server scoped to the host that
started it.

```sh
uv run things-agent-workflow
```

HTTP mode exists for local development:

```sh
THINGS_AGENT_TRANSPORT=http \
THINGS_AGENT_HOST=127.0.0.1 \
THINGS_AGENT_PORT=8013 \
uv run things-agent-workflow
```

> **Warning**: HTTP mode does not add authentication. Keep it bound to `127.0.0.1`; do not
> expose it to a LAN, VPN, container bridge, or public interface.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `THINGS_AGENT_TRANSPORT` | `stdio` | Set to `http` to enable local HTTP mode. Any other value uses stdio. |
| `THINGS_AGENT_HOST` | `127.0.0.1` | HTTP bind address. Used only in HTTP mode. |
| `THINGS_AGENT_PORT` | `8013` | HTTP port. Used only in HTTP mode. |
| `THINGS_AGENT_LOCK_PATH` | `~/.local/state/things-agent-workflow/write.lock` | File shared by all local server processes to serialize writes. |

The write lock waits up to 10 seconds. Readback waits up to 5 seconds and polls every 100
milliseconds. These timeouts are internal service defaults, not environment settings.

## Authorization and data access

Create operations use Things URLs without a token. Updates call `things.token()` and require
Things URLs to be enabled in the app. The token is read only when an update is prepared.

The service does not:

- store the token in its own configuration;
- return it through MCP;
- place it in process arguments;
- write directly to the Things database.

The generated update URL is passed to `osascript` through standard input. Treat debug traces,
process instrumentation, and modified launch code as sensitive because an update URL contains
the token while it is being executed.

Managed Things notes may contain issue links, repository paths, decisions, and human context.
Do not put credentials, private keys, access tokens, or transient plan files in them.

## Write sequence

Every mutation follows this order:

1. Validate input, destinations, tags, and state requirements.
2. Acquire the shared file lock.
3. Search again for the stable key.
4. Open one Things URL.
5. Poll the read-only database.
6. Compare managed metadata and the requested Things fields.
7. Return a verified receipt or an unconfirmed-write error.

The service never retries a submitted URL. A timeout is ambiguous: the write may have succeeded
with a delayed database update, or Things may have ignored part of it.

## Reconcile an unconfirmed write

When a tool reports that a request was submitted but could not be read back:

1. Do not call the mutation again automatically.
2. Wait for Things to finish processing, then call `resume_handoff` with the stable key or item
   ID.
3. Open the returned Things link and compare the title, notes, tags, schedule, destination, and
   completion state with the request.
4. If the item exists, keep it as the canonical item. Correct a missing field manually or make
   one separately authorized transition where the tool supports that change.
5. If a project exists but a standard heading is missing, add the heading manually. Re-running
   the builder returns `existing` and does not repair it.
6. If no item exists after the user checks Things, the user may explicitly authorize a new
   capture.

An `existing` response is not a retry. It reports the managed item already holding the key and
does not change it.

## Resolve a concurrent edit

`resume_handoff` returns `expected_modified`. A transition fails when that value no longer
matches the Things item.

1. Resume the item again.
2. Inspect the newer packet and Things fields.
3. Revalidate external sources that could have changed.
4. Decide whether the requested transition is still correct.
5. Submit a new transition with the new `expected_modified` only after that review.

Do not omit `expected_modified` merely to bypass a conflict.

## Troubleshooting

### The MCP host does not list the server

**Cause**: The host has not reloaded configuration, the project path is wrong, or `uv` is not at
the configured path.

**Fix**:

1. Restart the MCP host.
2. Confirm the absolute project path in the host configuration.
3. Run the server inventory directly:

```sh
cd ~/source/things-agent-workflow
uv run fastmcp list \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --json
```

**Verify**: The result contains all six tools.

### `workflow_status` cannot read Things

**Cause**: Things has not created a local database, the current macOS process cannot read it, or
the database location is unavailable.

**Fix**: Open Things once, confirm that the local library is present, and grant the terminal or
host the macOS file access it requests. Do not change or copy the database directly.

**Verify**:

```sh
uv run fastmcp call \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --target workflow_status \
  --json
```

### A state or person tag cannot be resolved

**Cause**: Things silently ignores unknown tags, so the service rejects them before writing.

**Fix**: Create the exact tag in Things. Tag title matching is case-insensitive, but duplicate
titles are ambiguous and must be resolved in Things.

**Verify**: Run `workflow_status` for `waiting`, `deferred`, `solo`, and `build`. Person tags are
checked during capture or transition.

### Updates say Things URL authorization is not enabled

**Cause**: Things URLs are disabled or their local token is unavailable.

**Fix**: In Things, open **Settings > General**, enable Things URLs, and use **Manage** to confirm
the feature is active. Never paste the token into the MCP request.

**Verify**: Resume the item, then retry the transition only with explicit user authorization.

### A write lock times out

**Cause**: Another local MCP process is preparing or verifying a Things write.

**Fix**: Let the other operation finish, inspect its result, and reconcile by stable key. The
lock file may remain on disk after normal use; its presence does not mean the lock is held.

**Verify**: A later read-only resume or review works. Retry a mutation only when the first
operation's result is known.

### Managed note metadata is malformed

**Cause**: The marker block or its schema JSON was edited manually.

**Fix**: Stop automated transitions for that item. Compare it with the managed-note format in
[Architecture](architecture.md), preserve the human-readable body, and repair the block only
after identifying the intended key, kind, ownership, and state. If identity is uncertain,
create no replacement automatically.

**Verify**: `resume_handoff` returns one item with parsed metadata.

### More than one item uses the same key

**Cause**: A manual copy, older automation, or ambiguous write created duplicate managed
identity.

**Fix**: Choose one canonical item in Things, preserve any unique context, and remove the
managed marker from the duplicate or cancel it. The service fails closed until exactly one
managed item owns the key.

**Verify**: `resume_handoff` returns the canonical item without a conflict.

## Upgrade and verify

Update the working copy without rewriting local history:

```sh
cd ~/source/things-agent-workflow
git pull --ff-only origin main
uv sync --frozen
uv run pytest --cov=things_agent_workflow --cov-report=term-missing
uv run ruff check .
uv build
```

Restart each MCP host after dependency, server, or skill changes. Run `workflow_status` before
the first mutation after an upgrade.

Managed notes currently use schema version 1. A future schema change needs an explicit migration
plan and tests; changing the parser alone is not a migration.

## Release checklist

Before tagging a release:

1. Confirm the worktree and staged diff contain only the intended change.
2. Run the full tests with coverage, Ruff, and `uv build`.
3. Run the read-only tool inventory and `workflow_status` smoke tests.
4. Confirm no automated test opened a live Things write.
5. Update [Changelog](../CHANGELOG.md) and the package version together.
6. Review any change to durable writes, authorization, metadata, or verification as controlled
   risk.
