#!/usr/bin/env python3
"""Port remaining V-Bounce epic/story files to ClearGate shape.

Resumes Batches 7B + 7C after subagent stall. Idempotent — skips if
target already exists. Deduplicates stories (prefers sprint-dir copy
over epic-dir copy when both exist).

Run with: backend/.venv/bin/python3 scripts/port-remaining.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required. Run with backend/.venv/bin/python3.")


REPO = Path(__file__).resolve().parent.parent
SRC_BACKLOG = REPO / "product_plans.vbounce-archive" / "backlog"
SRC_ARCHIVE_EPICS = REPO / "product_plans.vbounce-archive" / "archive" / "epics"
SRC_ARCHIVE_SPRINTS = REPO / "product_plans.vbounce-archive" / "archive" / "sprints"
DST_PENDING = REPO / ".cleargate" / "delivery" / "pending-sync"
DST_ARCHIVE = REPO / ".cleargate" / "delivery" / "archive"

SPRINT_SHIP_DATE = {
    "sprint-01": "2026-04-11",
    "sprint-02": "2026-04-11",
    "sprint-03": "2026-04-12",
    "sprint-04": "2026-04-12",
    "sprint-05": "2026-04-12",
    "sprint-06": "2026-04-12",
    "sprint-07": "2026-04-12",
    "sprint-08": "2026-04-13",
    "sprint-09": "2026-04-13",
    "sprint-10": "2026-04-13",
    "sprint-11": "2026-04-14",
}

SPRINT_ID_TO_LABEL = {k: f"S-{k.split('-')[1]}" for k in SPRINT_SHIP_DATE}

CLEARGATE_MIGRATION_DATE = "2026-04-24"
CLEARGATE_MIGRATION_TS = f"{CLEARGATE_MIGRATION_DATE}T00:00:00Z"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
INSTRUCTIONS_RE = re.compile(r"^<instructions>.*?</instructions>\s*\n+", re.DOTALL)


def parse_source(path: Path) -> tuple[dict, str]:
    """Return (frontmatter dict, body string). Body has leading <instructions> stripped."""
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, INSTRUCTIONS_RE.sub("", text).lstrip()
    fm_text, body = m.groups()
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    body = INSTRUCTIONS_RE.sub("", body).lstrip()
    return fm, body


def slugify(name: str) -> str:
    """EPIC-024_concurrency_hardening → EPIC-024-concurrency-hardening. Preserves existing hyphens + story numeric structure."""
    return name.replace("_", "-")


def kebab_story_id(story_id: str) -> str:
    """Keep story_id as-is (e.g. STORY-024-01) but strip any accidental quotes."""
    return str(story_id).strip().strip('"').strip("'")


def emoji_ambiguity(raw: str | None) -> str:
    """'🟢 Low' → '🟢'. Defaults to '🔴'."""
    if not raw:
        return "🔴"
    raw = str(raw)
    for e in ("🟢", "🟡", "🔴"):
        if e in raw:
            return e
    return "🔴"


def normalize_status_active(raw: str | None) -> str:
    """Map V-Bounce active/backlog statuses to ClearGate Draft/Ready/Active."""
    if not raw:
        return "Draft"
    r = str(raw).lower()
    if "done" in r or "completed" in r or "shipped" in r:
        return "Shipped"
    if "active" in r or "bouncing" in r or "execut" in r:
        return "Active"
    if "ready" in r:
        return "Ready"
    return "Draft"


def cleargate_frontmatter(kind: str, src_fm: dict, created_at: str, updated_at: str, status: str, approved: bool) -> str:
    """Build ClearGate YAML frontmatter block. kind in {'epic', 'story'}."""
    amb = emoji_ambiguity(src_fm.get("ambiguity"))
    lines = ["---"]
    if kind == "epic":
        eid = src_fm.get("epic_id") or ""
        lines.append(f'epic_id: "{eid}"')
        lines.append(f'status: "{status}"')
        lines.append(f'ambiguity: "{amb}"')
        lines.append('context_source: "PROPOSAL-001-teemo-platform.md"')
        owner = src_fm.get("owner", "") or "TBD"
        lines.append(f'owner: "{owner}"')
        target_date = src_fm.get("target_date", "") or "TBD"
        lines.append(f'target_date: "{target_date}"')
        if approved:
            lines.append("approved: true")
    elif kind == "story":
        sid = kebab_story_id(src_fm.get("story_id") or "")
        lines.append(f'story_id: "{sid}"')
        parent = src_fm.get("parent_epic_ref") or src_fm.get("parent_epic") or ""
        lines.append(f'parent_epic_ref: "{parent}"')
        lines.append(f'status: "{status}"')
        lines.append(f'ambiguity: "{amb}"')
        lines.append('context_source: "PROPOSAL-001-teemo-platform.md"')
        complexity = src_fm.get("complexity_label") or "L2"
        # Strip qualifier parens — "L1 (Trivial)" → "L1"
        complexity = re.sub(r"\s*\(.*\)", "", str(complexity)).strip()
        lines.append(f'complexity_label: "{complexity}"')
        lines.append("parallel_eligible: false")
        lines.append('expected_bounce_exposure: "low"')
        if approved:
            lines.append("approved: true")
    lines.append(f'created_at: "{created_at}"')
    lines.append(f'updated_at: "{updated_at}"')
    lines.append('created_at_version: "vbounce-backlog"')
    lines.append(f'updated_at_version: "cleargate-migration-{CLEARGATE_MIGRATION_DATE}"')
    lines.append("server_pushed_at_version: null")
    lines.append("draft_tokens:")
    lines.append("  input: null")
    lines.append("  output: null")
    lines.append("  cache_read: null")
    lines.append("  cache_creation: null")
    lines.append("  model: null")
    lines.append("  sessions: []")
    lines.append("cached_gate_result:")
    lines.append("  pass: null")
    lines.append("  failing_criteria: []")
    lines.append("  last_gate_check: null")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def provenance_note(src: Path, shipped_in: str | None) -> str:
    rel = src.relative_to(REPO)
    if shipped_in:
        return f"> **Ported from V-Bounce (shipped).** Original: `{rel}`. Shipped in sprint {shipped_in}, carried forward during ClearGate migration {CLEARGATE_MIGRATION_DATE}.\n\n"
    return f"> **Ported from V-Bounce.** Original: `{rel}`. Carried forward during ClearGate migration {CLEARGATE_MIGRATION_DATE}.\n\n"


def port_epic(src: Path, is_archived: bool, shipped_sprint_key: str | None = None) -> tuple[Path, bool]:
    """Transform an EPIC-*.md file. Returns (target_path, wrote). Skips if target exists."""
    fm, body = parse_source(src)
    slug = slugify(src.stem)
    dst_dir = DST_ARCHIVE if is_archived else DST_PENDING
    dst = dst_dir / f"{slug}.md"
    if dst.exists():
        return dst, False

    if is_archived:
        status = "Shipped"
        approved = True
        updated_at = f"{SPRINT_SHIP_DATE.get(shipped_sprint_key, '2026-04-14')}T00:00:00Z"
    else:
        status = normalize_status_active(fm.get("status"))
        approved = False
        updated_at = CLEARGATE_MIGRATION_TS

    created_at = "2026-04-10T00:00:00Z"
    shipped_label = SPRINT_ID_TO_LABEL.get(shipped_sprint_key, "S-XX") if is_archived else None

    out = cleargate_frontmatter("epic", fm, created_at, updated_at, status, approved)
    out += provenance_note(src, shipped_label)
    out += body.lstrip("\n")
    dst.write_text(out)
    return dst, True


def port_story(src: Path, is_archived: bool, shipped_sprint_key: str | None = None) -> tuple[Path, bool]:
    fm, body = parse_source(src)
    slug = slugify(src.stem)
    dst_dir = DST_ARCHIVE if is_archived else DST_PENDING
    dst = dst_dir / f"{slug}.md"
    if dst.exists():
        return dst, False

    if is_archived:
        status = "Shipped"
        approved = True
        updated_at = f"{SPRINT_SHIP_DATE.get(shipped_sprint_key, '2026-04-14')}T00:00:00Z"
    else:
        status = normalize_status_active(fm.get("status"))
        approved = False
        updated_at = CLEARGATE_MIGRATION_TS

    created_at = "2026-04-10T00:00:00Z"
    shipped_label = SPRINT_ID_TO_LABEL.get(shipped_sprint_key, "S-XX") if is_archived else None

    out = cleargate_frontmatter("story", fm, created_at, updated_at, status, approved)
    out += provenance_note(src, shipped_label)
    out += body.lstrip("\n")
    dst.write_text(out)
    return dst, True


def main():
    stats = {"active_epics": 0, "active_stories": 0, "archived_epics": 0, "archived_stories": 0, "skipped_exists": 0, "dedup_story_skipped": 0}

    # --- Active backlog (7B) ---
    for src in sorted(SRC_BACKLOG.rglob("EPIC-*.md")):
        if src.name.startswith("STORY"):
            continue
        _, wrote = port_epic(src, is_archived=False)
        if wrote:
            stats["active_epics"] += 1
        else:
            stats["skipped_exists"] += 1

    for src in sorted(SRC_BACKLOG.rglob("STORY-*.md")):
        _, wrote = port_story(src, is_archived=False)
        if wrote:
            stats["active_stories"] += 1
        else:
            stats["skipped_exists"] += 1

    # --- Archived epic-dir epics + stories (7C part 1) ---
    # Track archived story IDs as we write them from sprint dirs; prefer sprint-dir version.
    # To do this, do sprint dirs FIRST, then epic dirs, and skip any story ID already ported.
    ported_story_ids: set[str] = set()

    # Collect existing archived story IDs first (things the agents already wrote before stalling)
    for existing in DST_ARCHIVE.glob("STORY-*.md"):
        # filename shape STORY-006-01-foo.md → prefix STORY-006-01
        m = re.match(r"(STORY-[^-]+-[^-]+)", existing.stem)
        if m:
            ported_story_ids.add(m.group(1))

    # Archived stories via sprint dirs (canonical shipped versions)
    for sprint_dir in sorted(SRC_ARCHIVE_SPRINTS.iterdir()):
        if not sprint_dir.is_dir():
            continue
        sprint_key = sprint_dir.name  # e.g. "sprint-01"
        for src in sorted(sprint_dir.glob("STORY-*.md")):
            m = re.match(r"(STORY-[^-]+-[^-]+)", src.stem)
            prefix = m.group(1) if m else src.stem
            if prefix in ported_story_ids:
                stats["dedup_story_skipped"] += 1
                continue
            _, wrote = port_story(src, is_archived=True, shipped_sprint_key=sprint_key)
            if wrote:
                stats["archived_stories"] += 1
                ported_story_ids.add(prefix)
            else:
                stats["skipped_exists"] += 1

    # Archived epics from epics/ dir (7C part 2)
    # Sprint that shipped each epic — from INDEX.md
    epic_shipped = {
        "EPIC-004": "sprint-06",
        "EPIC-006": "sprint-08",
        "EPIC-007": "sprint-07",
        "EPIC-008": "sprint-09",
        "EPIC-013": "sprint-11",
        "EPIC-015": "sprint-11",
        "EPIC-016": "sprint-11",
    }
    for src in sorted(SRC_ARCHIVE_EPICS.rglob("EPIC-*.md")):
        if src.name.startswith("STORY"):
            continue
        # Determine which epic this is for ship-date lookup
        m = re.match(r"(EPIC-\d+)", src.stem)
        sprint_key = epic_shipped.get(m.group(1) if m else "", "sprint-11")
        _, wrote = port_epic(src, is_archived=True, shipped_sprint_key=sprint_key)
        if wrote:
            stats["archived_epics"] += 1
        else:
            stats["skipped_exists"] += 1

    # Archived stories in epic dirs (only the ones NOT already in a sprint dir)
    for src in sorted(SRC_ARCHIVE_EPICS.rglob("STORY-*.md")):
        m = re.match(r"(STORY-[^-]+-[^-]+)", src.stem)
        prefix = m.group(1) if m else src.stem
        if prefix in ported_story_ids:
            stats["dedup_story_skipped"] += 1
            continue
        # Map to the epic's shipping sprint
        epic_m = re.match(r"STORY-(\d+)-", src.stem)
        epic_id = f"EPIC-{epic_m.group(1)}" if epic_m else None
        sprint_key = epic_shipped.get(epic_id, "sprint-11")
        _, wrote = port_story(src, is_archived=True, shipped_sprint_key=sprint_key)
        if wrote:
            stats["archived_stories"] += 1
            ported_story_ids.add(prefix)
        else:
            stats["skipped_exists"] += 1

    print("=" * 60)
    print("Port remaining — summary")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    print(f"  pending-sync total now: {len(list(DST_PENDING.glob('*.md')))}")
    print(f"  archive total now: {len(list(DST_ARCHIVE.glob('*.md')))}")


if __name__ == "__main__":
    main()
