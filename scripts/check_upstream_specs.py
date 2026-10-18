#!/usr/bin/env python3
"""Check upstream tool documentation for specification changes.

Fetches official hook documentation for each supported tool and compares
key specification elements against our local snapshots in docs/upstream-specs/.

The checker deliberately extracts *surface* information only (event names and
payload field names).  It never generates or changes handler code: upstream
changes should always be reviewed before the snapshots or runtime behavior are
updated.

Usage:
    python scripts/check_upstream_specs.py [--tool TOOL]
"""

from __future__ import annotations

import argparse
import html as html_lib
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

# Candidate event-name patterns for each supported tool.  These intentionally
# match the naming convention of a tool rather than a fixed list of events so
# that newly-added upstream events can be discovered.  The structural parsing
# below (event tables/lists) is used first; these patterns are the fallback for
# pages/fixtures without recognisable sections.
EVENT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "claude": [re.compile(r"\b[A-Z][A-Za-z0-9]*\b")],
    "cursor": [re.compile(r"\b[a-z][A-Za-z0-9]*\b")],
    "codex": [re.compile(r"\b[A-Z][A-Za-z0-9]*\b")],
    "opencode": [re.compile(r"\b[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+\b")],
    "gemini": [re.compile(r"\b[A-Z][A-Za-z0-9]*\b")],
    "cline": [re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")],
    "copilot": [re.compile(r"\b[a-z][A-Za-z0-9]*\b")],
    "kiro": [re.compile(r"\b[A-Z][A-Za-z0-9]*\b")],
}

# A candidate must be valid for the naming convention used in the tool's event
# tables.  This is narrower than EVENT_PATTERNS so normal prose is not treated
# as an event when parsing Markdown/HTML tables and lists.
_EVENT_STYLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "claude": re.compile(r"^[A-Z][A-Za-z0-9]*$"),
    "cursor": re.compile(r"^[a-z][A-Za-z0-9]*$"),
    "codex": re.compile(r"^[A-Z][A-Za-z0-9]*$"),
    "opencode": re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$"),
    "gemini": re.compile(r"^[A-Z][A-Za-z0-9]*$"),
    "cline": re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"),
    "copilot": re.compile(r"^[a-z][A-Za-z0-9]*$"),
    "kiro": re.compile(r"^[A-Z][A-Za-z0-9]*$"),
}

# Headings that look like events but are table/section labels.  Tool-specific
# event names are never in this set.
_NON_EVENT_NAMES = frozenset({
    "Activation", "Agent", "Available", "Blockable", "Command", "Common",
    "Config", "Configuration", "Constraints", "Controllable", "Default",
    "Description", "Event", "Events", "Execution", "Experimental", "Field",
    "Fields", "File", "Hook", "Hooks", "Installation", "LSP", "Lifecycle",
    "Matcher", "Meaning", "Message", "Name", "No", "Output", "Permission",
    "Platforms", "Required", "Schema", "Server", "Session", "Shell",
    "Snapshot", "Source", "Specification", "Target", "Todo", "Tool", "Trigger",
    "TUI", "Type", "Types", "Yes",
})

_EVENT_HEADING_KEYS = frozenset({
    "events",
    "hook events",
    "available events",
    "documented hook events",
})
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_QUOTED_FIELD_RE = re.compile(
    r'"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"\s*:'
)
_BULLET_FIELD_RE = re.compile(
    r"^\s*[-*]\s+`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*:"
)
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")


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


def _html_to_text(raw: str) -> str:
    """Convert simple HTML to Markdown-ish text while preserving structure.

    Official documentation pages are HTML, while tests and snapshots are
    Markdown.  Keeping headings, table cells, and list items lets both forms go
    through the same extraction logic without adding an HTML parser dependency.
    """
    if "<" not in raw:
        return raw

    text = raw

    def _heading(match: re.Match[str]) -> str:
        level = len(match.group(1))
        title = re.sub(r"<[^>]+>", " ", match.group(2))
        return f"\n{'#' * level} {html_lib.unescape(title).strip()}\n"

    text = re.sub(
        r"<h([1-6])[^>]*>(.*?)</h\1\s*>",
        _heading,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<code[^>]*>(.*?)</code\s*>", r"`\1`", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</t[dh]\s*>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return html_lib.unescape(text)


def _clean_token(value: str) -> str:
    """Normalise a table cell, list item, or heading into a single token."""
    token = value.strip().strip("`*_ ")
    # A cell can contain descriptive text after the event name.  Event names
    # never contain whitespace, so the first token is sufficient.
    if not token:
        return ""
    token = token.split()[0]
    return token.strip("`*_,.;:()[]{}")


def _is_event_name(token: str, tool: str) -> bool:
    return bool(
        token
        and token not in _NON_EVENT_NAMES
        and _EVENT_STYLE_PATTERNS[tool].fullmatch(token)
    )


def _section_title_key(title: str) -> str:
    # Drop parenthetical counts such as "(33 total)".
    return re.sub(r"\s*\([^)]*\)\s*", " ", title).strip().lower()


def _is_event_section_title(title: str) -> bool:
    key = _section_title_key(title)
    if key in _EVENT_HEADING_KEYS:
        return True
    return (
        "event" in key
        and ("hook" in key or "available" in key)
    )


def _table_cells(line: str) -> list[str]:
    if "|" not in line:
        return []
    cells = [cell.strip() for cell in line.split("|")]
    # Leading/trailing pipes produce empty edge cells.
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _iter_sections(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    """Return (level, title, body lines) for every Markdown heading section."""
    sections: list[tuple[int, str, list[str]]] = []
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    for pos, (start, level, title) in enumerate(headings):
        end = len(lines)
        for next_start, next_level, _ in headings[pos + 1:]:
            if next_level <= level:
                end = next_start
                break
        sections.append((level, title, lines[start + 1:end]))
    return sections


def _extract_events_from_lines(lines: list[str], tool: str) -> set[str]:
    """Extract event names from tables, lists, and nested headings."""
    events: set[str] = set()

    for line in lines:
        cells = _table_cells(line)
        if cells:
            token = _clean_token(cells[0])
            if _is_event_name(token, tool):
                events.add(token)

        heading = _HEADING_RE.match(line)
        if heading:
            token = _clean_token(heading.group(2))
            if _is_event_name(token, tool):
                events.add(token)
        elif line.lstrip().startswith(("-", "*")):
            content = line.lstrip()[1:].strip()
            token = _clean_token(content)
            if _is_event_name(token, tool):
                events.add(token)

    return events


def _extract_events_from_sections(text: str, tool: str) -> set[str]:
    lines = text.splitlines()
    events: set[str] = set()
    for _level, title, body in _iter_sections(lines):
        if _is_event_section_title(title):
            events.update(_extract_events_from_lines(body, tool))
    return events


def _extract_broad_events(text: str, tool: str) -> set[str]:
    events: set[str] = set()
    for pattern in EVENT_PATTERNS[tool]:
        events.update(pattern.findall(text))
    return {event for event in events if event not in _NON_EVENT_NAMES}


def extract_events_from_html(html: str, tool: str) -> set[str]:
    """Extract hook event names from upstream HTML (or a Markdown fixture)."""
    text = _html_to_text(html)
    events = _extract_events_from_sections(text, tool)
    if events:
        return events

    # No recognisable "Hook Events"/"Available Events" section.  Try a
    # structural scan first, then fall back to tokens for small fixtures.
    events = _extract_events_from_lines(text.splitlines(), tool)
    if events:
        return events
    return _extract_broad_events(text, tool)


def extract_events_from_spec(spec_path: Path, tool: str | None = None) -> set[str]:
    """Extract hook event names from our local spec markdown."""
    text = spec_path.read_text()
    tool = tool or tool_name_from_path(spec_path)
    events = _extract_events_from_sections(text, tool)
    if events:
        return events

    events = _extract_events_from_lines(text.splitlines(), tool)
    if events:
        return events
    return _extract_broad_events(text, tool)


def tool_name_from_path(spec_path: Path) -> str:
    """Infer the tool name from a snapshot path (e.g. claude.md -> claude)."""
    return spec_path.stem


def _extract_table_fields(lines: list[str]) -> set[str]:
    """Extract field names from tables whose header is field-oriented."""
    fields: set[str] = set()
    header: list[str] | None = None

    for line in lines:
        cells = _table_cells(line)
        if not cells:
            header = None
            continue

        # Separator row (e.g. |---|---|) leaves header unchanged.
        if all(_TABLE_SEPARATOR_RE.match(cell) for cell in cells if cell):
            continue

        if header is None:
            header = [cell.lower() for cell in cells]
            continue

        if any(
            marker in cell
            for cell in header
            for marker in ("field", "parameter", "property")
        ):
            token = _clean_token(cells[0])
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", token):
                fields.add(token)

    return fields


def _extract_fields_from_text(text: str) -> set[str]:
    fields = set(_QUOTED_FIELD_RE.findall(text))
    for line in text.splitlines():
        match = _BULLET_FIELD_RE.match(line)
        if match:
            fields.add(match.group(1).rstrip("."))
    fields.update(_extract_table_fields(text.splitlines()))
    return fields


def extract_json_fields_from_spec(spec_path: Path) -> set[str]:
    """Extract payload field names from JSON examples and field lists."""
    return _extract_fields_from_text(spec_path.read_text())


def extract_fields_from_html(html: str) -> set[str]:
    """Extract payload field names from upstream HTML/Markdown."""
    return _extract_fields_from_text(_html_to_text(html))


def _apply_diff(
    diffs: list[SpecDiff],
    tool: str,
    upstream: set[str],
    local: set[str],
    added_category: str,
    removed_category: str,
    label: str,
) -> None:
    added = upstream - local
    removed = local - upstream
    if added:
        diffs.append(SpecDiff(
            tool,
            added_category,
            f"New {label} in upstream: {sorted(added)}",
        ))
    if removed:
        diffs.append(SpecDiff(
            tool,
            removed_category,
            f"{label.capitalize()} removed from upstream: {sorted(removed)}",
        ))


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

    spec_text = spec_path.read_text()
    local_events = extract_events_from_spec(spec_path, tool)
    upstream_events = extract_events_from_html(html, tool)

    # For broad fallback extraction, remove tokens that already occur as
    # non-event prose in the local snapshot.  This keeps simple fixtures useful
    # without turning ordinary prose changes into event-drift reports.
    upstream_text = _html_to_text(html)
    if not _extract_events_from_sections(upstream_text, tool):
        local_noise = _extract_broad_events(spec_text, tool) - local_events
        upstream_events -= local_noise

    _apply_diff(
        diffs, tool, upstream_events, local_events,
        "new_events", "removed_events", "events",
    )

    local_fields = extract_json_fields_from_spec(spec_path)
    upstream_fields = extract_fields_from_html(html)
    _apply_diff(
        diffs, tool, upstream_fields, local_fields,
        "new_fields", "removed_fields", "payload fields",
    )

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
        if tool not in UPSTREAM_URLS:
            print(f"  {tool}: unknown tool (supported: {', '.join(sorted(UPSTREAM_URLS))})")
            return 2
        print(f"  {tool}: fetching {UPSTREAM_URLS[tool]} ...")
        tool_diffs = check_tool(tool)
        all_diffs.extend(tool_diffs)

    if not all_diffs:
        print("\nAll specs are up to date.")
        return 0

    print(f"\n{'='*60}")
    print(f"Found {len(all_diffs)} difference(s):\n")
    for d in all_diffs:
        icon = {
            "new_events": "+", "removed_events": "-",
            "new_fields": "+", "removed_fields": "-",
            "fetch": "!", "missing": "?", "config": "?",
        }.get(d.category, "~")
        print(f"  [{icon}] {d.tool}/{d.category}: {d.detail}")

    print(f"\nRun with --tool <name> to check a specific tool.")
    print(f"Update specs in {SPECS_DIR}/ after reviewing changes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
