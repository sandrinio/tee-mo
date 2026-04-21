"""Citation collector for Tee-Mo agent tool calls (STORY-017-09).

Source-producing agent tools (search_wiki, read_wiki_page, read_document,
web_search, crawl_page, http_request) append Citation records to the list
living on ``AgentDeps.citations`` during tool execution. After the agent
run completes, ``slack_dispatch`` reads the list and renders a Block Kit
SOURCES footer under the reply.

Design rules:
  - Tools append on success only. Errors and empty results contribute nothing.
  - ``source_id`` is the dedupe key; same source cited twice renders once.
  - Order of first occurrence is preserved (more-relevant sources surface first).
  - Records are dataclasses — simple, hashable by ``source_id`` after dedupe.

Keeping this module free of pydantic-ai / Supabase imports so it can be
unit-tested in isolation and reused if a non-Slack surface ever needs
citations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CitationKind = Literal["wiki", "document", "web"]


@dataclass(frozen=True)
class Citation:
    """A single source the agent used while producing a reply.

    Attributes:
        kind:      Coarse source category — drives chip grouping and the
                   fallback category label when ``category`` is None.
        title:    Human-readable label shown on the chip (e.g. the doc
                   filename, wiki page title, or web page title).
        url:       Optional absolute URL the chip links to. When None the
                   chip renders as plain text (no link).
        category:  Optional muted label rendered next to the title (e.g.
                   the source doc title a wiki page came from, the web
                   host, etc.). When None the chip omits the category.
        source_id: Stable identity for dedupe. Tools pick a key that
                   uniquely names the source (doc UUID, wiki slug, URL
                   for web). Two records with the same ``source_id``
                   collapse to one chip.
    """

    kind: CitationKind
    title: str
    url: str | None
    category: str | None
    source_id: str


def dedupe_and_cap(citations: list[Citation], max_display: int = 5) -> tuple[list[Citation], int]:
    """Collapse duplicate citations by ``source_id`` and cap the display count.

    Preserves first-occurrence order so the earliest-mentioned source is
    rendered first — matches conversational intuition that the source the
    agent reached for first is the most relevant.

    Args:
        citations:   Raw list from ``AgentDeps.citations`` (may contain dupes).
        max_display: Maximum chips to render before overflowing into a
                     "+N more" tail chip. Default 5.

    Returns:
        Tuple of (displayed_citations, overflow_count). ``overflow_count``
        is 0 when nothing was cut; >0 triggers a trailing "+N more" chip
        in the Block Kit builder.
    """
    seen: set[str] = set()
    deduped: list[Citation] = []
    for c in citations:
        if c.source_id in seen:
            continue
        seen.add(c.source_id)
        deduped.append(c)

    if len(deduped) <= max_display:
        return deduped, 0
    return deduped[:max_display], len(deduped) - max_display
