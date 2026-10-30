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
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "docs" / "upstream-specs"

UPSTREAM_URLS: dict[str, str] = {
    "claude": "https://code.claude.com/docs/en/hooks",
    "cursor": "https://cursor.com/ja/docs/hooks",
    "codex": "https://learn.chatgpt.com/docs/config-file/config-reference",
    "opencode": "https://opencode.ai/docs/plugins/",
    "gemini": "https://geminicli.com/docs/hooks/",
    "cline": "https://docs.cline.bot/sdk/plugins",
    "copilot": "https://docs.github.com/en/copilot/reference/hooks-reference",
    "kiro": "https://kiro.dev/docs/hooks/",
}

# A candidate must fit the tool's event naming convention before it is accepted.
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

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET_FIELD_RE = re.compile(
    r"^\s*[-*]\s+`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*:"
)
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")

# Live checks compare only documented, named regions. A tool without a stable
# event or payload section is reported as unsupported instead of diffing page prose.
UPSTREAM_EVENT_SECTIONS = {
    "claude": {"hook events"},
    "cursor": {"hook events"},
    "codex": set(),
    "opencode": {"events", "compaction hooks"},
    "gemini": {"hook events"},
    "cline": set(),
    "copilot": {"hook events"},
    "kiro": set(),
}
SNAPSHOT_EVENT_SECTIONS = {
    "claude": {"hook events"},
    "cursor": {"hook events"},
    "codex": {"documented hook events"},
    "opencode": {"available events"},
    "gemini": {"hook events"},
    "cline": {"hook events"},
    "copilot": {"hook events"},
    "kiro": {"hook events"},
}
UPSTREAM_PAYLOAD_SECTIONS = {
    "claude": {"common input fields"},
    "cursor": {"input (all hooks)"},
    "codex": set(),
    "opencode": set(),
    "gemini": set(),
    "cline": set(),
    "copilot": {"hook event input payloads", "notification hook"},
    "kiro": set(),
}
SNAPSHOT_PAYLOAD_SECTIONS = {
    "claude": {"common input fields", "common input fields (all events)"},
    "cursor": {"common input fields", "common input fields (all events)"},
    "codex": set(),
    "opencode": set(),
    "gemini": set(),
    "cline": set(),
    "copilot": {
        "payload formats (camelcase and vs code compatible pascalcase / snake_case)",
        "per-event input schemas",
    },
    "kiro": set(),
}
UPSTREAM_UNSUPPORTED_REASONS = {
    ("codex", "event"): "configured reference has no dedicated event list",
    ("cline", "event"): "configured SDK page has no authoritative hook event registry",
    ("kiro", "event"): "configured Hooks page links to a separate Hook types registry",
    ("codex", "payload"): "configured reference has no dedicated hook payload section",
    ("opencode", "payload"): "configured Events page has no payload field schema",
    ("gemini", "payload"): "configured hooks page has no explicit payload field section",
    ("cline", "payload"): "configured SDK page has no hook payload schema",
    ("kiro", "payload"): "configured Hooks page has no payload field schema",
}
UPSTREAM_PARTIAL_REASONS = {
    ("claude", "payload"): (
        "only the common input field table is comparable; event-specific examples mix top-level and nested tool schemas"
    ),
    ("cursor", "payload"): (
        "only common input fields are compared; event-specific input schemas are not extracted"
    ),
}


@dataclass
class SpecDiff:
    tool: str
    category: str
    detail: str


@dataclass
class Surface:
    values: set[str] | None
    reason: str | None = None


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

    # Page metadata and styling are not part of the documented hook surface.
    text = re.sub(r"<!--.*?-->", " ", raw, flags=re.DOTALL)
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", text,
                  flags=re.IGNORECASE | re.DOTALL)

    def _pre_block(match: re.Match[str]) -> str:
        content = re.sub(r"<[^>]+>", " ", match.group(1))
        return f"\n```text\n{html_lib.unescape(content)}\n```\n"

    text = re.sub(r"<pre\b[^>]*>(.*?)</pre\s*>", _pre_block, text,
                  flags=re.IGNORECASE | re.DOTALL)

    def _heading(match: re.Match[str]) -> str:
        level = int(match.group(1))
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
    # Drop numeric section counts without erasing meaningful labels like "(all hooks)".
    title = title.replace("\u200b", "")
    title = re.sub(r"\s*\(\d+[^)]*\)", "", title).strip().lower()
    return " ".join(title.split())


def _table_cells(line: str) -> list[str]:
    if "|" not in line:
        return []
    cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line)]
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


def _event_tokens(value: str, tool: str, table_label: bool = False) -> set[str]:
    """Read event identifiers only when a cell or heading presents them as code."""
    value = value.replace("\u200b", "")
    candidates = re.findall(r"`([^`]+)`", value)
    if not candidates:
        candidates = [part.strip() for part in re.split(r"\s*/\s*", value.strip().strip("|*_ "))]
    if table_label and tool == "copilot":
        candidates = [
            (parts[0].lower() + "".join(word.title() for word in parts[1:])) if len(parts) > 1 else candidate
            for candidate in candidates
            if (parts := candidate.split()) and all(re.fullmatch(r"[A-Za-z]+", word) for word in parts)
        ]
    events = set()
    for candidate in candidates:
        for part in re.split(r"\s*/\s*", candidate.strip()):
            token = part.strip("`*_ ")
            if _is_event_name(token, tool):
                events.add(token)
    return events


def _events_in_lines(lines: list[str], tool: str, heading_level: int,
                     allow_lists: bool = False) -> set[str]:
    events: set[str] = set()
    event_column = None
    for line in lines:
        cells = _table_cells(line)
        if cells:
            headers = [re.sub(r"[^a-z ]", "", cell.lower()).strip() for cell in cells]
            header_column = next((i for i, value in enumerate(headers)
                                  if value in {"event", "event name", "hook event", "hook event name"}), None)
            if header_column is not None:
                event_column = header_column
                continue
            if all(_TABLE_SEPARATOR_RE.match(cell) for cell in cells if cell):
                continue
            if any(value in {"field", "input field", "output field", "property", "type"}
                   for value in headers):
                event_column = None
                continue
            if event_column is not None:
                if event_column >= len(cells):
                    raise ValueError("event table row is missing its event column")
                values = _event_tokens(cells[event_column], tool, table_label=True)
                if not values:
                    raise ValueError("event table contains a row without a parseable identifier")
                events.update(values)
            continue
        if not line.strip():
            continue
        event_column = None
        heading = _HEADING_RE.match(line)
        if heading and len(heading.group(1)) == heading_level:
            events.update(_event_tokens(heading.group(2), tool))
        elif allow_lists and line.lstrip().startswith(("-", "*")):
            events.update(_event_tokens(line.lstrip()[1:].strip(), tool))
    return events


def _surface(text: str, tool: str, sections: dict[str, set[str]],
             parser, surface_name: str) -> Surface:
    wanted = sections.get(tool)
    if not wanted:
        reason = UPSTREAM_UNSUPPORTED_REASONS.get((tool, surface_name),
                                                   f"no configured {surface_name} section")
        return Surface(None, reason)
    matches = [(level, title, body) for level, title, body in _iter_sections(text.splitlines())
               if _section_title_key(title) in wanted]
    if not matches:
        return Surface(None, f"no recognized {surface_name} section")
    try:
        values = parser(matches, tool)
    except ValueError as error:
        return Surface(None, str(error))
    if not values:
        return Surface(None, f"recognized {surface_name} section contained no parseable fields")
    return Surface(values)


def _event_surface(html: str, tool: str, snapshot: bool = False) -> Surface:
    text = html if snapshot else _html_to_text(html)
    sections = SNAPSHOT_EVENT_SECTIONS if snapshot else UPSTREAM_EVENT_SECTIONS

    def parse(matches, name):
        events: set[str] = set()
        for level, title, body in matches:
            events.update(_events_in_lines(body, name, level + 1, allow_lists=name == "opencode"))
            if name == "opencode" and _section_title_key(title) == "compaction hooks":
                source = "\n".join(body)
                for token in re.findall(r"[\"']([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)[\"']\s*:", source):
                    if _is_event_name(token, name):
                        events.add(token)
        return events

    return _surface(text, tool, sections,
                    parse, "event")


def _payload_surface(text: str, tool: str, snapshot: bool = False) -> Surface:
    sections = SNAPSHOT_PAYLOAD_SECTIONS if snapshot else UPSTREAM_PAYLOAD_SECTIONS

    source = text if snapshot else _html_to_text(text)
    matches = [(level, title, body) for level, title, body in _iter_sections(source.splitlines())
               if _section_title_key(title) in sections.get(tool, set())]
    if not matches:
        reason = UPSTREAM_UNSUPPORTED_REASONS.get((tool, "payload"), "no recognized payload section")
        return Surface(None, reason)

    def parse(matches, _tool):
        values: set[str] = set()
        for level, title, body in matches:
            key = _section_title_key(title)
            if tool == "claude" and not snapshot:
                # The common-field table is the comparable surface; event
                # examples also contain arbitrary nested tool-input schemas.
                values.update(_extract_table_fields(body))
            elif tool == "copilot" and snapshot and key.startswith("payload formats"):
                common = re.search(r"```[^\n]*\n(.*?)```", "\n".join(body), re.DOTALL)
                if common:
                    values.update(_extract_fields_from_text(f"```json\n{common.group(1)}\n```"))
                values.update(_extract_table_fields(body))
            else:
                values.update(_extract_payload_fields_from_text(
                    "\n".join(body),
                ))
        return values

    try:
        values = parse(matches, tool)
    except ValueError as error:
        return Surface(None, str(error))
    if not values:
        return Surface(None, "recognized payload section contained no parseable fields")
    partial_reason = UPSTREAM_PARTIAL_REASONS.get((tool, "payload")) if not snapshot else None
    return Surface(values, partial_reason)


def extract_events_from_html(html: str, tool: str) -> set[str]:
    """Extract identifiers from the tool's explicitly named event section."""
    result = _event_surface(html, tool)
    return result.values or set()


def extract_events_from_spec(spec_path: Path, tool: str | None = None) -> set[str]:
    """Extract hook event names from our local spec markdown."""
    tool = tool or tool_name_from_path(spec_path)
    result = _event_surface(spec_path.read_text(), tool, snapshot=True)
    return result.values or set()


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
            if not line.strip():
                continue
            header = None
            continue

        # Separator row (e.g. |---|---|) leaves header unchanged.
        if all(_TABLE_SEPARATOR_RE.match(cell) for cell in cells if cell):
            continue

        if header is None:
            header = [cell.lower() for cell in cells]
            continue

        header_keys = [re.sub(r"[^a-z ]", "", cell).strip() for cell in header]
        field_column = next((index for index, key in enumerate(header_keys)
                             if key in {"field", "field name", "input field", "output field",
                                        "parameter", "property", "property name"}), None)
        if field_column is not None and field_column < len(cells):
            token = _clean_token(cells[field_column])
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", token):
                fields.add(token)
            continue

        additional_column = next((index for index, key in enumerate(header_keys)
                                  if key in {"additional fields", "input fields"}), None)
        if additional_column is not None and additional_column < len(cells):
            value = cells[additional_column]
            for match in re.finditer(r"`([A-Za-z_][A-Za-z0-9_.]*)`", value):
                before = value[:match.start()].rstrip()
                after = value[match.end():].lstrip()
                if before.endswith(":"):
                    continue
                if not after or after.startswith((",", ":", "(")):
                    fields.add(match.group(1))

    return fields


def _extract_fields_from_text(text: str) -> set[str]:
    fields: set[str] = set()
    code_blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    code_blocks.extend(re.findall(r"`([^`]*[{}][^`]*)`", text, re.DOTALL))
    for block in code_blocks:
        fields.update(_top_level_object_fields(block))
    for line in text.splitlines():
        match = _BULLET_FIELD_RE.match(line)
        if match:
            fields.add(match.group(1).rstrip("."))
    fields.update(_extract_table_fields(text.splitlines()))
    return fields


def _top_level_object_fields(block: str) -> set[str]:
    """Read only keys at the root of a JSON or TypeScript-like object example."""
    start = block.find("{")
    end = block.rfind("}")
    if start < 0 or end < start:
        return set()
    candidate = block[start:end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict):
        return {key for key in value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", key)}

    fields: set[str] = set()
    depth = 0
    index = 0
    while index < len(candidate):
        char = candidate[index]
        if char in {"\"", "'"}:
            quote = char
            end = index + 1
            escaped = False
            while end < len(candidate):
                if escaped:
                    escaped = False
                elif candidate[end] == "\\":
                    escaped = True
                elif candidate[end] == quote:
                    break
                end += 1
            key = candidate[index + 1:end]
            after = end + 1
            while after < len(candidate) and candidate[after].isspace():
                after += 1
            if depth == 1 and after < len(candidate) and candidate[after] == ":":
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", key):
                    fields.add(key)
            index = end + 1
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 1 and re.match(r"[A-Za-z_]", char):
            end = index + 1
            while end < len(candidate) and re.match(r"[A-Za-z0-9_.]", candidate[end]):
                end += 1
            after = end
            while after < len(candidate) and candidate[after].isspace():
                after += 1
            if after < len(candidate) and candidate[after] == "?":
                after += 1
                while after < len(candidate) and candidate[after].isspace():
                    after += 1
            if after < len(candidate) and candidate[after] == ":":
                fields.add(candidate[index:end])
            index = end
            continue
        index += 1
    return fields


def _extract_payload_fields_from_text(text: str) -> set[str]:
    """Extract input fields while excluding clearly marked output examples."""
    selected: list[str] = []
    in_output = False
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading and len(heading.group(1)) >= 3:
            in_output = False
        if re.match(r"^\s*(?:#{1,6}\s*)?Output(?:\s*\([^)]*\))?\s*:",
                    line, re.IGNORECASE):
            in_output = True
        if not in_output:
            selected.append(line)
    return _extract_fields_from_text("\n".join(selected))


def extract_json_fields_from_spec(spec_path: Path) -> set[str]:
    """Extract payload field names from explicitly named snapshot sections."""
    result = _payload_surface(spec_path.read_text(), tool_name_from_path(spec_path), snapshot=True)
    return result.values or set()


def extract_fields_from_html(html: str, tool: str = "claude") -> set[str]:
    """Extract payload field names only from explicitly named payload sections."""
    result = _payload_surface(html, tool)
    return result.values or set()


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

    for name, upstream, local, added, removed, label in (
        ("events", _event_surface(html, tool), _event_surface(spec_path.read_text(), tool, snapshot=True),
         "new_events", "removed_events", "events"),
        ("payload", _payload_surface(html, tool),
         _payload_surface(spec_path.read_text(), tool, snapshot=True),
         "new_fields", "removed_fields", "payload fields"),
    ):
        if upstream.reason or local.reason:
            reason = upstream.reason or local.reason
            diffs.append(SpecDiff(tool, f"unsupported_{name}", reason or "surface unavailable"))
            if upstream.values is not None and local.values is not None:
                _apply_diff(diffs, tool, upstream.values, local.values,
                            added, removed, label)
            continue
        _apply_diff(diffs, tool, upstream.values or set(), local.values or set(),
                    added, removed, label)

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
    print(f"Found {len(all_diffs)} difference(s) or unsupported surface(s):\n")
    for d in all_diffs:
        icon = {
            "new_events": "+", "removed_events": "-",
            "new_fields": "+", "removed_fields": "-",
            "fetch": "!", "missing": "?", "config": "?",
            "unsupported_events": "?", "unsupported_payload": "?",
        }.get(d.category, "~")
        print(f"  [{icon}] {d.tool}/{d.category}: {d.detail}")

    print(f"\nRun with --tool <name> to check a specific tool.")
    print(f"Update specs in {SPECS_DIR}/ after reviewing changes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
