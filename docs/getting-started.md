# Getting started

Install this service on the Mac that runs Things 3. The MCP server reads the local Things
database and opens documented Things URLs for writes, so it is not a remote service and does
not belong on a headless host.

## Prerequisites

Before installing, confirm that the Mac has:

- Things 3 installed with a local database;
- Things URLs enabled under **Things > Settings > General > Enable Things URLs**;
- `uv` available at `/opt/homebrew/bin/uv`;
- Python 3.12 or later, which `uv` can install for the project;
- access to the private GitLab or GitHub repository.

Enabling Things URLs creates the local authorization token used for updates. The service reads
that token from the Things database when needed. Do not copy it into MCP configuration, shell
variables, logs, or repository files.

Create these tags in Things before using their states:

| Tag | Requirement |
| --- | --- |
| `waiting` | Required when a handoff enters `waiting`. |
| `deferred` | Required when a handoff enters `deferred`. |
| `solo` | Optional marker for Nick-only work. |
| `build` | Optional marker for Nick-plus-agent work. |
| Person tag, such as `@damon` | Optional, but it must already exist before a tool can apply it. |

## Install the project

Clone from either configured remote. The GitLab repository is the primary example here.

```sh
cd ~/source
git clone git@github.com:NickCrew/things-agent-workflow.git
cd things-agent-workflow
uv sync --frozen
```

Verify that the installed server exposes six tools:

```sh
uv run fastmcp list \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --json
```

The result should list `capture_handoff`, `resume_handoff`, `transition_handoff`,
`review_handoffs`, `build_workstream_project`, and `workflow_status`.

## Configure Codex

Add the server beside the existing `things-mcp` entry in `~/.codex/config.toml`. Replace the
project path if the clone lives elsewhere.

```toml
[mcp_servers.things-workflow]
command = "/opt/homebrew/bin/uv"
args = [
    "run",
    "--project",
    "/Users/nick.ferguson/source/things-agent-workflow",
    "things-agent-workflow",
]
startup_timeout_sec = 120
```

Do not remove the general-purpose `things` server. The two servers have different jobs:
`things-mcp` supports ordinary Things operations, while `things-workflow` enforces the managed
handoff contract.

## Configure Claude

Add this entry under the top-level `mcpServers` object in `~/.claude.json`:

```json
{
  "mcpServers": {
    "things-workflow": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "run",
        "--project",
        "/Users/nick.ferguson/source/things-agent-workflow",
        "things-agent-workflow"
      ]
    }
  }
}
```

Merge the `things-workflow` entry into the existing `mcpServers` object. Do not replace the rest
of the file.

## Link the skills

The repository is the canonical source for four user-invoked skills:

- `remind-me`
- `track-this`
- `things-review`
- `things-project`

Create links only where no file or directory already occupies the destination:

```sh
workflow_repo="$HOME/source/things-agent-workflow"
mkdir -p "$HOME/.codex/skills" "$HOME/.agents/skills" "$HOME/.claude/skills"

for skill in remind-me track-this things-review things-project; do
  ln -s "$workflow_repo/skills/$skill" "$HOME/.codex/skills/$skill"
  ln -s "$workflow_repo/skills/$skill" "$HOME/.agents/skills/$skill"
  ln -s "$workflow_repo/skills/$skill" "$HOME/.claude/skills/$skill"
done
```

If a destination already exists, inspect and back it up before replacing it. Do not merge two
skill directories by hand. Each host should resolve the complete skill directory from this
repository.

For Claude, merge these entries into `skillOverrides` in `~/.claude/settings.json`:

```json
{
  "skillOverrides": {
    "remind-me": "user-invocable-only",
    "track-this": "user-invocable-only",
    "things-review": "user-invocable-only",
    "things-project": "user-invocable-only"
  }
}
```

The `agents/openai.yaml` file in each skill already disables implicit Codex invocation.

Restart Codex and Claude after changing their MCP or skill configuration.

## Verify Things access

Run the read-only status tool from the project directory:

```sh
uv run fastmcp call \
  --command '/opt/homebrew/bin/uv run things-agent-workflow' \
  --target workflow_status \
  --json
```

A ready installation reports:

- `read_access: true`;
- `required_state_tags.waiting: true`;
- `required_state_tags.deferred: true`;
- counts for the Areas and projects visible in the local Things database.

The `solo` and `build` tags are optional. A `false` value means ownership still works, but the
corresponding visual marker will not be applied.

This check does not create or update anything. Continue with [Workflows](workflows.md) when the
status is healthy, or [Operations](operations.md) when it is not.
