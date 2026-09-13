from __future__ import annotations

import asyncio
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote

from fastmcp import Client

from things_agent_workflow.server import mcp

ROOT = Path(__file__).parents[1]
MARKDOWN_FILES = [
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    *sorted((ROOT / "docs").glob("*.md")),
]


def test_local_markdown_links_resolve() -> None:
    missing = []
    for path in MARKDOWN_FILES:
        for target in re.findall(r"(?<!!)\[[^]]+]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            relative = unquote(target.split("#", 1)[0])
            if relative and not (path.parent / relative).resolve().exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    assert missing == []


def test_structured_documentation_examples_parse() -> None:
    problems = []
    for path in MARKDOWN_FILES:
        text = path.read_text()
        for index, block in enumerate(
            re.findall(r"```json\n(.*?)\n```", text, re.DOTALL), start=1
        ):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.relative_to(ROOT)} JSON block {index}: {exc}")
        for index, block in enumerate(
            re.findall(r"```toml\n(.*?)\n```", text, re.DOTALL), start=1
        ):
            try:
                tomllib.loads(block)
            except tomllib.TOMLDecodeError as exc:
                problems.append(f"{path.relative_to(ROOT)} TOML block {index}: {exc}")
    assert problems == []


def test_tool_reference_matches_mcp_input_schemas() -> None:
    reference = (ROOT / "docs" / "tool-reference.md").read_text()

    async def compare() -> list[str]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        problems = []
        for tool in tools:
            heading = f"## `{tool.name}`"
            if heading not in reference:
                problems.append(f"missing section: {tool.name}")
                continue
            section = reference.split(heading, 1)[1].split("\n## ", 1)[0]
            if "### Parameters" in section:
                parameter_section = section.split("### Parameters", 1)[1].split(
                    "\n### ", 1
                )[0]
                documented = set(
                    re.findall(r"^\| `([^`]+)` \|", parameter_section, re.MULTILINE)
                )
            else:
                documented = set()
            actual = set(tool.input_schema.get("properties", {}))
            if documented != actual:
                problems.append(
                    f"{tool.name}: missing={sorted(actual - documented)}, "
                    f"extra={sorted(documented - actual)}"
                )
        return problems

    assert asyncio.run(compare()) == []
