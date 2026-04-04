#!/usr/bin/env python3
"""Check upstream tool documentation for specification changes.

Fetches official hook documentation for each supported tool and compares
key specification elements against our local snapshots in docs/upstream-specs/.

Usage:
    python scripts/check_upstream_specs.py [--tool TOOL]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "docs" / "upstream-specs"

UPSTREAM_URLS: dict[str, str] = {
    "claude": "https://code.claude.com/docs/en/hooks",
    "cursor": "https://cursor.com/docs/hooks",
    "codex": "https://developers.openai.com/codex/config-reference",
    "opencode": "https://opencode.ai/docs/plugins/",
    "gemini": "https://geminicli.com/docs/hooks/",
    "cline": "https://docs.cline.bot/customization/hooks",
    "copilot": "https://docs.github.com/en/copilot/reference/hooks-configuration",
    "kiro": "https://kiro.dev/docs/cli/hooks/",
}

# Patterns to extract key specification elements from HTML/text
EVENT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "claude": [
        re.compile(r"(?:SessionStart|SessionEnd|PreToolUse|PostToolUse|PostToolUseFailure|"
                   r"UserPromptSubmit|Stop|StopFailure|Notification|SubagentStart|SubagentStop|"
                   r"TaskCreated|TaskCompleted|TeammateIdle|ConfigChange|CwdChanged|FileChanged|"
                   r"WorktreeCreate|WorktreeRemove|PreCompact|PostCompact|Elicitation|"
                   r"ElicitationResult|PermissionRequest|PermissionDenied|InstructionsLoaded)")
    ],
    "gemini": [
        re.compile(r"(?:SessionStart|SessionEnd|BeforeAgent|AfterAgent|BeforeModel|AfterModel|"
                   r"BeforeToolSelection|BeforeTool|AfterTool|PreCompress|Notification)")
    ],
    "cline": [
        re.compile(r"(?:TaskStart|TaskResume|TaskCancel|TaskComplete|PreToolUse|PostToolUse|"
                   r"UserPromptSubmit|PreCompact)")
    ],
    "copilot": [
        re.compile(r"(?:sessionStart|sessionEnd|userPromptSubmitted|preToolUse|postToolUse|"
                   r"errorOccurred)")
    ],
    "kiro": [
        re.compile(r"(?:agentSpawn|userPromptSubmit|preToolUse|postToolUse|stop)")
    ],
}


@dataclass
class SpecDiff:
    tool: str
    category: str
    detail: str


def fetch_page(url: str, timeout: int = 30) -> str:
    """Fetch a URL and return its text content."""
    req = urllib.request.Request(url, headers={"User-Agent": "otel-hooks-spec-checker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_events_from_html(html: str, tool: str) -> set[str]:
    """Extract hook event names from HTML content."""
    events: set[str] = set()
    patterns = EVENT_PATTERNS.get(tool, [])
    for pat in patterns:
        events.update(pat.findall(html))
    return events


def extract_events_from_spec(spec_path: Path) -> set[str]:
    """Extract hook event names from our local spec markdown."""
    text = spec_path.read_text()
    events: set[str] = set()

    # Match event names from markdown tables (| EventName | ...)
    for line in text.splitlines():
        if "|" in line:
            cells = [c.strip() for c in line.split("|")]
            for cell in cells:
                # Match PascalCase or camelCase event names
                if re.match(r"^[A-Z][a-zA-Z]+$", cell) and cell not in (
                    "Event", "Description", "Blockable", "Matcher", "Type",
                    "Field", "Required", "Default", "Yes", "No",
                ):
                    events.add(cell)
                elif re.match(r"^[a-z][a-zA-Z]+$", cell) and cell not in (
                    "string", "number", "boolean", "object", "array",
                    "command", "http", "prompt", "agent",
                ):
                    events.add(cell)

    # Match backtick-quoted event names
    for m in re.finditer(r"`([A-Z][a-zA-Z]+)`", text):
        name = m.group(1)
        if name not in ("Path", "Global", "Project", "Local", "Unix"):
            events.add(name)

    return events


def extract_json_fields_from_spec(spec_path: Path) -> set[str]:
    """Extract JSON field names from code blocks in our spec."""
    text = spec_path.read_text()
    fields: set[str] = set()
    in_json = False
    for line in text.splitlines():
        if line.strip().startswith("```json"):
            in_json = True
            continue
        if line.strip() == "```":
            in_json = False
            continue
        if in_json:
            for m in re.finditer(r'"(\w+)":', line):
                fields.add(m.group(1))
    return fields


def check_tool(tool: str) -> list[SpecDiff]:
    """Check a single tool for upstream changes."""
    diffs: list[SpecDiff] = []
    spec_path = SPECS_DIR / f"{tool}.md"

    if not spec_path.exists():
        diffs.append(SpecDiff(tool, "missing", f"No local spec at {spec_path}"))
        return diffs

    url = UPSTREAM_URLS.get(tool)
    if not url:
        diffs.append(SpecDiff(tool, "config", f"No upstream URL configured for {tool}"))
        return diffs

    try:
        html = fetch_page(url)
    except Exception as e:
        diffs.append(SpecDiff(tool, "fetch", f"Failed to fetch {url}: {e}"))
        return diffs

    # Check for new events in upstream
    upstream_events = extract_events_from_html(html, tool)
    local_events = extract_events_from_spec(spec_path)

    if upstream_events:
        new_events = upstream_events - local_events
        removed_events = local_events - upstream_events
        if new_events:
            diffs.append(SpecDiff(tool, "new_events", f"New events in upstream: {sorted(new_events)}"))
        if removed_events:
            diffs.append(SpecDiff(tool, "removed_events", f"Events removed from upstream: {sorted(removed_events)}"))

    # Check for significant content changes (page size heuristic)
    spec_text = spec_path.read_text()
    snapshot_line = next(
        (l for l in spec_text.splitlines() if l.startswith("> Snapshot:")), ""
    )

    # Extract JSON field names mentioned in upstream
    upstream_fields: set[str] = set()
    for m in re.finditer(r'"(\w+)"', html):
        upstream_fields.add(m.group(1))

    local_fields = extract_json_fields_from_spec(spec_path)

    # Only report field diffs for fields that look like payload fields
    payload_fields = {
        "session_id", "transcript_path", "cwd", "hook_event_name",
        "tool_name", "tool_input", "tool_response", "tool_use_id",
        "permission_mode", "agent_id", "agent_type", "prompt",
        "timestamp", "toolName", "toolArgs", "toolResult",
        "taskId", "hookName", "workspaceRoots",
    }
    new_payload_fields = (upstream_fields & payload_fields) - local_fields
    if new_payload_fields:
        diffs.append(SpecDiff(
            tool, "new_fields",
            f"New payload fields in upstream: {sorted(new_payload_fields)}"
        ))

    if not diffs:
        print(f"  {tool}: OK (no drift detected)")

    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="Check upstream spec changes")
    parser.add_argument("--tool", help="Check a specific tool only")
    args = parser.parse_args()

    tools = [args.tool] if args.tool else sorted(UPSTREAM_URLS.keys())
    all_diffs: list[SpecDiff] = []

    print(f"Checking {len(tools)} tool(s) against upstream docs...\n")

    for tool in tools:
        print(f"  {tool}: fetching {UPSTREAM_URLS[tool]} ...")
        tool_diffs = check_tool(tool)
        all_diffs.extend(tool_diffs)

    if not all_diffs:
        print("\nAll specs are up to date.")
        return 0

    print(f"\n{'='*60}")
    print(f"Found {len(all_diffs)} difference(s):\n")
    for d in all_diffs:
        icon = {"new_events": "+", "removed_events": "-", "new_fields": "+",
                "fetch": "!", "missing": "?", "config": "?"}.get(d.category, "~")
        print(f"  [{icon}] {d.tool}/{d.category}: {d.detail}")

    print(f"\nRun with --tool <name> to check a specific tool.")
    print(f"Update specs in {SPECS_DIR}/ after reviewing changes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
