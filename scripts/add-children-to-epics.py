#!/usr/bin/env python3
"""Add `children: [...]` arrays to each epic's frontmatter so ClearGate wiki
lint doesn't complain about missing backlinks.

Scans all stories in .cleargate/delivery/, groups by parent_epic_ref, and
inserts a children list into the matching epic's frontmatter. Idempotent.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required. Run with backend/.venv/bin/python3.")


REPO = Path(__file__).resolve().parent.parent
DELIVERY = REPO / ".cleargate" / "delivery"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def read_doc(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.groups()
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def parent_epic_normalized(raw: str | None) -> str | None:
    """Normalize parent refs like 'EPIC-005 Phase A' → 'EPIC-005', 'ADR-026 (...)' → None."""
    if not raw:
        return None
    s = str(raw).strip()
    m = re.match(r"EPIC-\d+", s)
    return m.group(0) if m else None


def main():
    # 1. Collect all story -> parent-epic mappings
    epic_children: dict[str, list[str]] = defaultdict(list)

    for story_path in sorted(DELIVERY.rglob("STORY-*.md")):
        fm, _ = read_doc(story_path)
        parent = parent_epic_normalized(fm.get("parent_epic_ref"))
        if not parent:
            continue
        story_file_id = story_path.stem  # e.g. STORY-024-01-database-queue-rpc
        epic_children[parent].append(story_file_id)

    # 2. For each epic file, rewrite frontmatter to include children array
    updated = 0
    for epic_path in sorted(DELIVERY.rglob("EPIC-*.md")):
        m = re.match(r"(EPIC-\d+)", epic_path.stem)
        if not m:
            continue
        epic_id = m.group(1)
        children = sorted(epic_children.get(epic_id, []))
        if not children:
            continue

        text = epic_path.read_text()
        fm_match = FRONTMATTER_RE.match(text)
        if not fm_match:
            continue

        fm_text = fm_match.group(1)
        body = fm_match.group(2)

        # Remove any existing children: ... (single-line or block form)
        fm_lines = fm_text.split("\n")
        new_lines: list[str] = []
        skip_block = False
        for line in fm_lines:
            if skip_block:
                if line.startswith(" ") or line.startswith("-"):
                    continue
                skip_block = False
            if re.match(r"^children:\s*\[.*\]\s*$", line):
                continue  # drop inline form
            if re.match(r"^children:\s*$", line):
                skip_block = True
                continue
            new_lines.append(line)

        # Insert children after `status:` for readability
        inserted = False
        out_lines: list[str] = []
        children_yaml = "children:\n" + "\n".join(f'  - "{c}"' for c in children)
        for line in new_lines:
            out_lines.append(line)
            if not inserted and line.startswith("status:"):
                out_lines.append(children_yaml)
                inserted = True
        if not inserted:
            out_lines.append(children_yaml)

        new_fm = "\n".join(out_lines).strip("\n")
        new_text = f"---\n{new_fm}\n---\n{body}"
        epic_path.write_text(new_text)
        updated += 1
        print(f"  {epic_path.relative_to(REPO)}: {len(children)} children")

    print()
    print(f"Updated {updated} epic files.")


if __name__ == "__main__":
    main()
