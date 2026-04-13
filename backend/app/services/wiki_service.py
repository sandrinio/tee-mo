"""
Wiki ingest pipeline — EPIC-013, STORY-013-02.

Decomposes workspace documents into structured wiki pages using a scan-tier
LLM. Each document produces a source-summary page plus concept and entity
pages. Pages are upserted into ``teemo_wiki_pages`` with cross-references
linking related pages across the workspace.

Design decisions:
  - LLM access follows the same module-reference pattern as scan_service.py:
    ``_agent_module.Agent`` is accessed via the imported module object (not a
    direct from-import) so that tests can monkeypatch the globals before calling
    this module. See FLASHCARDS.md httpx pattern for the same principle.
  - Tiny document threshold: documents with content < 100 chars skip LLM ingest
    entirely and are immediately marked ``synced``. Agent reads them via
    ``read_document`` fallback (sprint-context rule).
  - Slug normalization: LLM-provided slugs are normalised via regex to ensure
    kebab-case consistency. Duplicates within a single ingest batch get a numeric
    suffix.
  - ``source_document_ids`` is stored as ``[document_id]`` (UUID array) for the
    initial ingest. Cross-referencing does not change this column.
  - ``created_at`` / ``updated_at`` are omitted from all insert/update payloads —
    they are managed by DB defaults (FLASHCARDS: omit DEFAULT NOW() columns).
  - Upsert key is ``(workspace_id, slug)`` unique constraint for idempotent
    re-ingest.
  - Cross-referencing uses simple word-overlap on titles/tldr fields — cheap,
    no extra LLM calls, sufficient for the routing use case.

Prompt design notes (v2 — tuned after AI judge evaluation):
  - Always request exactly 1 source-summary page, N concept pages, N entity pages.
  - Explicit rules for spreadsheets/tabular data to avoid low-quality concept pages.
  - TLDRs explicitly capped at 500 chars with routing guidance (help agent decide
    which page to read).
  - Page count guidance (3-15) to avoid over-/under-segmentation.
  - Slugs must be descriptive and unique within the document.
  - JSON output wrapped in a code fence to allow the model to produce clean JSON
    even when it adds preamble text.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents import agent as _agent_module
from app.services import document_service as _document_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ADR-004 scan-tier model IDs — same mapping as scan_service.SCAN_TIER_MODELS
SCAN_TIER_MODELS: dict[str, str] = {
    "google": "gemini-2.5-flash",
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
}

#: Documents shorter than this character count are skipped — set synced immediately.
#: Sprint-context rule: "Tiny doc threshold: Skip wiki ingest for docs < 100 chars."
TINY_DOC_THRESHOLD = 100

# ---------------------------------------------------------------------------
# Ingest prompt (v2 — tuned against AI judge evaluation)
# ---------------------------------------------------------------------------

_WIKI_INGEST_SYSTEM_PROMPT = """\
You are a wiki editor. Given a source document, decompose it into structured wiki pages.

Output ONLY a JSON array (no prose, no markdown fences) where each element has these exact fields:
- slug: kebab-case identifier, descriptive and unique (e.g., "onboarding-process", "john-smith")
- title: Human-readable title
- page_type: one of "source-summary", "concept", "entity"
- content: Full markdown content for this wiki page (self-contained and useful on its own)
- tldr: 1-2 sentence summary that helps decide whether to read the full page (max 500 chars)
- suggested_related_topics: list of topic strings this page relates to

Rules:
- Always create exactly 1 "source-summary" page that summarizes the entire document
- Create "concept" pages for each major theme, process, or idea (workflows, policies, methodologies)
- Create "entity" pages for named things (people, tools, departments, products, systems)
- Each page must be self-contained and useful on its own without reading the source
- TLDRs must help an AI agent decide whether to read this page for a given query — be specific
- Slugs must be descriptive and unique within this document; use the entity/concept name directly
- Avoid vague slugs like "overview" or "summary" — use "employee-handbook-overview" instead
- For spreadsheets/tabular data: create 1 summary page + entity pages for key data categories
  (e.g., for a financial spreadsheet: "q3-financial-summary" + "revenue-breakdown" + "expense-categories")
  Do NOT create concept pages for column headers or data types
- Target 3-15 pages per document depending on length and complexity
- Short documents (< 1K words): 3-5 pages; Medium (1K-5K): 5-10 pages; Long (> 5K): 10-15 pages
- Do NOT hallucinate entities — only create entity pages for things explicitly named in the source
- Remove duplicate or overlapping concepts — merge them into one page

Output: raw JSON array only, starting with [ and ending with ].
"""

# Fallback prompt for retry — simpler, more likely to produce valid JSON
_WIKI_INGEST_FALLBACK_PROMPT = """\
You are a wiki editor. Parse the source document and return a JSON array.

Return ONLY valid JSON — no text before or after. Each element:
{"slug": "kebab-slug", "title": "Title", "page_type": "source-summary|concept|entity",
 "content": "markdown content", "tldr": "1-2 sentence max 500 chars",
 "suggested_related_topics": ["topic1", "topic2"]}

Requirements: exactly 1 source-summary, plus concept and entity pages for the document.
Output only the JSON array starting with [.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_slug(raw_slug: str) -> str:
    """Normalize a slug to lowercase kebab-case.

    Replaces any character that is not a lowercase letter, digit, or hyphen
    with a hyphen, then strips leading/trailing hyphens and collapses runs.

    Args:
        raw_slug: Raw slug string (possibly from LLM output with spaces or caps).

    Returns:
        Clean kebab-case slug string.
    """
    slug = raw_slug.lower()
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _deduplicate_slugs(pages: list[dict]) -> list[dict]:
    """Ensure all slugs in a page list are unique by appending a numeric suffix.

    Modifies the ``slug`` field in place when duplicates are found.

    Args:
        pages: List of page dicts with ``slug`` field.

    Returns:
        The same list with duplicate slugs resolved.
    """
    seen: dict[str, int] = {}
    for page in pages:
        slug = page["slug"]
        if slug in seen:
            seen[slug] += 1
            page["slug"] = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 0
    return pages


def _parse_llm_json(raw_output: str) -> list[dict] | None:
    """Attempt to parse JSON from an LLM response string.

    Handles the common case where the model wraps JSON in a code fence
    (```json ... ```) or adds preamble prose before the array.

    Args:
        raw_output: Raw string returned by the LLM.

    Returns:
        Parsed list of page dicts, or None if parsing fails entirely.
    """
    text = raw_output.strip()

    # Strip markdown code fence if present (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first line (```json or ```) and last line (```)
        inner_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    # Find the first [ and last ] to extract the JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None

    json_str = text[start : end + 1]
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError:
        return None


def _extract_pages(
    raw_output: str,
    document_id: str,
) -> list[dict]:
    """Parse and validate wiki pages from LLM output.

    Normalizes slugs, ensures required fields, and deduplicates slugs
    within the batch.

    Args:
        raw_output: Raw LLM response string containing JSON.
        document_id: Document UUID — stored in source_document_ids array.

    Returns:
        List of validated and normalized page dicts ready for upsert.
        Empty list if parsing fails.
    """
    parsed = _parse_llm_json(raw_output)
    if not parsed:
        logger.warning("wiki_service: failed to parse LLM JSON output")
        return []

    pages: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue

        # Required fields — skip items missing slug, title, or page_type
        raw_slug = item.get("slug", "")
        title = item.get("title", "")
        page_type = item.get("page_type", "concept")

        if not raw_slug or not title:
            logger.debug("wiki_service: skipping page with missing slug or title: %s", item)
            continue

        slug = _normalize_slug(str(raw_slug))
        if not slug:
            # Fallback: derive slug from title
            slug = _normalize_slug(title)

        content = item.get("content", "") or ""
        tldr_raw = item.get("tldr", "") or ""
        # Enforce 500 char cap on tldr
        tldr = tldr_raw[:500] if len(tldr_raw) > 500 else tldr_raw

        suggested_related_topics = item.get("suggested_related_topics", [])
        if not isinstance(suggested_related_topics, list):
            suggested_related_topics = []

        pages.append(
            {
                "slug": slug,
                "title": title,
                "page_type": page_type if page_type in ("source-summary", "concept", "entity") else "concept",
                "content": content,
                "tldr": tldr,
                "suggested_related_topics": suggested_related_topics,
                "related_slugs": [],  # populated in cross-reference pass
                "source_document_ids": [document_id],
            }
        )

    return _deduplicate_slugs(pages)


def _compute_cross_references(
    new_pages: list[dict],
    existing_pages: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Identify related slugs between new and existing pages via word overlap.

    For each new page, checks if any significant words from its title appear
    in existing pages' titles or tldr strings (and vice versa). Populates
    ``related_slugs`` on both sides.

    Only words longer than 3 characters are considered to avoid noise from
    common short words (the, and, for, etc.).

    Args:
        new_pages: Pages just generated for the document being ingested.
        existing_pages: Pages already in the workspace from other documents.

    Returns:
        Tuple of (updated_new_pages, updated_existing_pages) with related_slugs set.
    """

    def _word_set(text: str) -> set[str]:
        """Extract significant lowercase words (> 3 chars) from text."""
        words = re.findall(r"[a-z]{4,}", text.lower())
        return set(words)

    for new_page in new_pages:
        new_words = _word_set(new_page["title"] + " " + new_page.get("tldr", ""))
        new_slugs: list[str] = new_page.get("related_slugs", [])

        for existing_page in existing_pages:
            ex_words = _word_set(
                existing_page.get("title", "") + " " + existing_page.get("tldr", "")
            )
            overlap = new_words & ex_words
            if overlap:
                existing_slug = existing_page.get("slug", "")
                if existing_slug and existing_slug not in new_slugs:
                    new_slugs.append(existing_slug)

                # Bidirectional: update existing page's related_slugs too
                ex_related: list[str] = existing_page.get("related_slugs", [])
                if new_page["slug"] not in ex_related:
                    ex_related.append(new_page["slug"])
                    existing_page["related_slugs"] = ex_related

        new_page["related_slugs"] = new_slugs

    return new_pages, existing_pages


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------


async def _call_ingest_llm(
    content: str,
    provider: str,
    api_key: str,
    *,
    use_fallback_prompt: bool = False,
) -> str:
    """Call the scan-tier LLM to decompose a document into wiki page JSON.

    Uses the same module-reference pattern as scan_service so tests can
    monkeypatch _agent_module.Agent and model classes before calling this.

    Args:
        content: Full document text to decompose.
        provider: BYOK provider slug — "google", "anthropic", or "openai".
        api_key: Decrypted plaintext BYOK API key.
        use_fallback_prompt: If True, use the simpler fallback system prompt.

    Returns:
        Raw LLM response string (expected to contain a JSON array).
    """
    model_id = SCAN_TIER_MODELS[provider]
    _agent_module._ensure_model_imports(provider)
    model = _agent_module._build_pydantic_ai_model(model_id, provider, api_key)

    system_prompt = (
        _WIKI_INGEST_FALLBACK_PROMPT if use_fallback_prompt else _WIKI_INGEST_SYSTEM_PROMPT
    )
    scan_agent = _agent_module.Agent(model, system_prompt=system_prompt)

    result = await scan_agent.run(content)
    return result.output


# ---------------------------------------------------------------------------
# Sync status helper
# ---------------------------------------------------------------------------


def _set_sync_status(supabase: Any, document_id: str, workspace_id: str, status: str) -> None:
    """Update the sync_status column on a teemo_documents row.

    Args:
        supabase:     Authenticated Supabase client.
        document_id:  UUID of the document.
        workspace_id: UUID of the owning workspace (for isolation guard).
        status:       One of: "processing", "synced", "error", "pending".
    """
    (
        supabase.table("teemo_documents")
        .update({"sync_status": status})
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ingest_document(
    supabase: Any,
    workspace_id: str,
    document_id: str,
    provider: str,
    api_key: str,
) -> dict:
    """Ingest a document from teemo_documents into structured wiki pages.

    Reads the document's ``content`` column, calls the scan-tier LLM to
    decompose it into wiki pages (source-summary + concept + entity pages),
    upserts the pages into ``teemo_wiki_pages``, runs a cross-reference pass
    against existing workspace pages, and logs the operation in ``teemo_wiki_log``.

    Tiny document threshold: documents with fewer than 100 characters of content
    are not sent to the LLM. They are immediately marked ``synced`` and the agent
    reads them via ``read_document`` fallback (sprint-context rule).

    Sync status transitions:
      - Before LLM call: ``processing``
      - On success: ``synced``
      - On failure: ``error``

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace.
        document_id:  UUID of the document to ingest.
        provider:     BYOK provider slug — "google", "anthropic", or "openai".
        api_key:      Decrypted plaintext BYOK API key.

    Returns:
        Dict with keys:
          ``pages_created`` (int): Total number of wiki pages upserted.
          ``page_types`` (dict): Mapping of page_type → count.
    """
    # Read document content
    content = await _document_service.read_document_content(
        supabase, workspace_id, document_id
    )

    # Tiny document threshold — skip ingest, mark synced immediately
    if not content or len(content) < TINY_DOC_THRESHOLD:
        logger.info(
            "wiki_service: skipping tiny document %s (len=%d)",
            document_id,
            len(content) if content else 0,
        )
        _set_sync_status(supabase, document_id, workspace_id, "synced")
        _log_wiki_operation(
            supabase,
            workspace_id=workspace_id,
            document_id=document_id,
            pages_created=0,
            status="synced",
            detail="Tiny document threshold — skipped ingest.",
        )
        return {"pages_created": 0, "page_types": {}}

    # Set status to processing before LLM call (R6)
    _set_sync_status(supabase, document_id, workspace_id, "processing")

    try:
        # Call scan-tier LLM — attempt once, retry with fallback prompt on JSON failure
        raw_output = await _call_ingest_llm(content, provider, api_key)
        pages = _extract_pages(raw_output, document_id)

        if not pages:
            # First attempt failed to produce valid pages — retry with simpler prompt
            logger.info(
                "wiki_service: retrying ingest for document %s with fallback prompt",
                document_id,
            )
            raw_output = await _call_ingest_llm(
                content, provider, api_key, use_fallback_prompt=True
            )
            pages = _extract_pages(raw_output, document_id)

        # Cross-reference: load existing workspace pages and find related slugs
        existing_pages = _fetch_existing_pages(supabase, workspace_id)
        pages, updated_existing = _compute_cross_references(pages, existing_pages)

        # Upsert new pages into teemo_wiki_pages
        pages_created = 0
        page_type_counts: dict[str, int] = {}

        for page in pages:
            payload = {
                "workspace_id": workspace_id,
                "slug": page["slug"],
                "title": page["title"],
                "page_type": page["page_type"],
                "content": page["content"],
                "tldr": page["tldr"],
                "related_slugs": page.get("related_slugs", []),
                "source_document_ids": page["source_document_ids"],
            }
            # Upsert on (workspace_id, slug) unique constraint — omit created_at/updated_at
            (
                supabase.table("teemo_wiki_pages")
                .upsert(payload, on_conflict="workspace_id,slug")
                .execute()
            )
            pages_created += 1
            pt = page["page_type"]
            page_type_counts[pt] = page_type_counts.get(pt, 0) + 1

        # Update related_slugs on existing pages that gained new cross-references
        for ex_page in updated_existing:
            if ex_page.get("related_slugs"):
                (
                    supabase.table("teemo_wiki_pages")
                    .update({"related_slugs": ex_page["related_slugs"]})
                    .eq("workspace_id", workspace_id)
                    .eq("slug", ex_page["slug"])
                    .execute()
                )

        # Mark document as synced (R6)
        _set_sync_status(supabase, document_id, workspace_id, "synced")

        # Log the operation
        _log_wiki_operation(
            supabase,
            workspace_id=workspace_id,
            document_id=document_id,
            pages_created=pages_created,
            status="synced",
            detail=f"Ingested {pages_created} pages: {page_type_counts}",
        )

        logger.info(
            "wiki_service: ingested document %s → %d pages %s",
            document_id,
            pages_created,
            page_type_counts,
        )

        return {"pages_created": pages_created, "page_types": page_type_counts}

    except Exception as exc:
        logger.error(
            "wiki_service: ingest failed for document %s: %s",
            document_id,
            exc,
            exc_info=True,
        )
        # Set error status (R6)
        _set_sync_status(supabase, document_id, workspace_id, "error")

        # Log failure
        _log_wiki_operation(
            supabase,
            workspace_id=workspace_id,
            document_id=document_id,
            pages_created=0,
            status="error",
            detail=str(exc),
        )
        raise


async def reingest_document(
    supabase: Any,
    workspace_id: str,
    document_id: str,
    provider: str,
    api_key: str,
) -> dict:
    """Destructively re-ingest a document — deletes old pages and re-runs ingest.

    Deletes ALL wiki pages where ``source_document_ids`` contains the given
    document UUID, then calls ``ingest_document`` from scratch. Finishes with
    a cross-reference pass that links new pages to pages from other documents.

    This is the correct call when document content has been updated and the
    wiki pages need to be regenerated (e.g., after a Drive sync or user edit).

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace.
        document_id:  UUID of the document whose pages to delete and regenerate.
        provider:     BYOK provider slug.
        api_key:      Decrypted plaintext BYOK API key.

    Returns:
        Same format as ``ingest_document``: ``{ pages_created: int, page_types: dict }``.
    """
    # Delete all existing pages for this document
    # teemo_wiki_pages.source_document_ids is UUID[] — use Supabase cs() for array contains
    (
        supabase.table("teemo_wiki_pages")
        .delete()
        .eq("workspace_id", workspace_id)
        .cs("source_document_ids", [document_id])
        .execute()
    )
    logger.info(
        "wiki_service: deleted existing pages for document %s (workspace %s)",
        document_id,
        workspace_id,
    )

    # Run full ingest from scratch
    return await ingest_document(supabase, workspace_id, document_id, provider, api_key)


async def rebuild_wiki_index(
    supabase: Any,
    workspace_id: str,
) -> list[dict]:
    """Return the wiki index for a workspace — list of { slug, title, tldr }.

    This is what gets injected into the agent's system prompt via
    ``_build_system_prompt`` in ``agent.py``. Returns all wiki pages in the
    workspace ordered by title.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the workspace.

    Returns:
        List of dicts, each with ``slug``, ``title``, and ``tldr`` keys.
        Empty list if no pages exist.
    """
    result = (
        supabase.table("teemo_wiki_pages")
        .select("slug, title, tldr")
        .eq("workspace_id", workspace_id)
        .order("title")
        .execute()
    )
    return result.data or []


async def lint_wiki(supabase: Any, workspace_id: str) -> str:
    """Scan the workspace wiki for structural quality issues and return a markdown report.

    Performs four checks — all via DB queries, NO LLM calls:

    1. **Orphan pages** — pages with no incoming ``related_slugs`` from any other
       page in the workspace. A page is considered orphaned when its slug does not
       appear in ANY other page's ``related_slugs`` array.

    2. **Stale pages** — wiki pages whose ``source_document_ids`` reference one or
       more documents whose ``sync_status`` is ``'pending'``. Stale pages have
       been superseded by updated source content but have not been re-ingested yet.

    3. **Missing summaries** — documents in ``teemo_documents`` that have no
       corresponding ``source-summary`` page in ``teemo_wiki_pages``. These are
       documents the wiki pipeline has not yet covered.

    4. **Low confidence** — wiki pages with ``confidence='low'``, indicating pages
       the ingest pipeline flagged as low-quality.

    Logs the operation in ``teemo_wiki_log`` with ``operation='lint'``.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the workspace to lint.

    Returns:
        A markdown-formatted health report string beginning with
        ``## Wiki Health Report``.
    """
    # ------------------------------------------------------------------
    # 1. Fetch all wiki pages for the workspace
    # ------------------------------------------------------------------
    pages_result = (
        supabase.table("teemo_wiki_pages")
        .select("slug, title, related_slugs, source_document_ids, page_type, confidence")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    all_pages: list[dict] = pages_result.data or []

    # ------------------------------------------------------------------
    # 2. Orphan detection — pages whose slug does not appear in any
    #    other page's related_slugs array.
    # ------------------------------------------------------------------
    # Build a set of all slugs that are referenced by at least one other page.
    referenced_slugs: set[str] = set()
    for page in all_pages:
        for ref_slug in (page.get("related_slugs") or []):
            referenced_slugs.add(ref_slug)

    orphan_pages: list[dict] = [
        page for page in all_pages
        if page["slug"] not in referenced_slugs
    ]

    # ------------------------------------------------------------------
    # 3. Stale page detection — pages referencing documents with
    #    sync_status='pending'.
    # ------------------------------------------------------------------
    # Fetch all documents in the workspace that are pending re-sync.
    pending_docs_result = (
        supabase.table("teemo_documents")
        .select("id")
        .eq("workspace_id", workspace_id)
        .eq("sync_status", "pending")
        .execute()
    )
    pending_doc_ids: set[str] = {
        row["id"] for row in (pending_docs_result.data or [])
    }

    stale_pages: list[dict] = []
    if pending_doc_ids:
        for page in all_pages:
            src_ids = set(page.get("source_document_ids") or [])
            if src_ids & pending_doc_ids:
                stale_pages.append(page)

    # ------------------------------------------------------------------
    # 4. Missing summaries — documents with no source-summary wiki page.
    # ------------------------------------------------------------------
    # Fetch all documents in the workspace.
    all_docs_result = (
        supabase.table("teemo_documents")
        .select("id, title")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    all_docs: list[dict] = all_docs_result.data or []

    # Build a set of document IDs that already have a source-summary page.
    covered_doc_ids: set[str] = set()
    for page in all_pages:
        if page.get("page_type") == "source-summary":
            for doc_id in (page.get("source_document_ids") or []):
                covered_doc_ids.add(doc_id)

    missing_summary_docs: list[dict] = [
        doc for doc in all_docs
        if doc["id"] not in covered_doc_ids
    ]

    # ------------------------------------------------------------------
    # 5. Low confidence pages.
    # ------------------------------------------------------------------
    low_confidence_pages: list[dict] = [
        page for page in all_pages
        if page.get("confidence") == "low"
    ]

    # ------------------------------------------------------------------
    # 6. Assemble markdown report
    # ------------------------------------------------------------------
    lines: list[str] = [
        "## Wiki Health Report",
        "",
        f"- {len(orphan_pages)} orphan page(s)",
        f"- {len(stale_pages)} stale page(s)",
        f"- {len(missing_summary_docs)} document(s) missing wiki pages",
        f"- {len(low_confidence_pages)} low-confidence page(s)",
    ]

    if orphan_pages or stale_pages or missing_summary_docs or low_confidence_pages:
        lines.append("")
        lines.append("### Details")

    if orphan_pages:
        lines.append("")
        lines.append("**Orphan Pages** (no incoming links from other pages):")
        for p in orphan_pages:
            lines.append(f"- `{p['slug']}` — {p.get('title', '')}")

    if stale_pages:
        lines.append("")
        lines.append("**Stale Pages** (source document has pending updates):")
        for p in stale_pages:
            lines.append(f"- `{p['slug']}` — {p.get('title', '')}")

    if missing_summary_docs:
        lines.append("")
        lines.append("**Documents Missing Wiki Coverage**:")
        for d in missing_summary_docs:
            lines.append(f"- `{d['id']}` — {d.get('title', 'Untitled')}")

    if low_confidence_pages:
        lines.append("")
        lines.append("**Low-Confidence Pages**:")
        for p in low_confidence_pages:
            lines.append(f"- `{p['slug']}` — {p.get('title', '')}")

    report = "\n".join(lines)

    # ------------------------------------------------------------------
    # 7. Log the lint operation
    # ------------------------------------------------------------------
    summary = (
        f"Lint: {len(orphan_pages)} orphans, {len(stale_pages)} stale, "
        f"{len(missing_summary_docs)} missing coverage, "
        f"{len(low_confidence_pages)} low confidence."
    )
    _log_lint_operation(supabase, workspace_id=workspace_id, detail=summary)

    logger.info(
        "wiki_service: lint_wiki workspace=%s — %s",
        workspace_id,
        summary,
    )

    return report


# ---------------------------------------------------------------------------
# Internal helpers — not part of the public API
# ---------------------------------------------------------------------------


def _fetch_existing_pages(supabase: Any, workspace_id: str) -> list[dict]:
    """Fetch slug, title, and tldr for all existing wiki pages in a workspace.

    Used by the cross-reference pass to find related pages across documents.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the workspace.

    Returns:
        List of page dicts with ``slug``, ``title``, ``tldr``, and ``related_slugs``.
    """
    result = (
        supabase.table("teemo_wiki_pages")
        .select("slug, title, tldr, related_slugs")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return result.data or []


def _log_lint_operation(
    supabase: Any,
    *,
    workspace_id: str,
    detail: str,
) -> None:
    """Insert a log entry into teemo_wiki_log for a lint operation.

    Logs the outcome of a lint scan for observability. Uses ``operation='lint'``
    and stores the summary in the ``details`` JSONB column. Lint is workspace-wide
    so there is no ``document_id`` in this payload.
    ``created_at`` is managed by the DB default — omitted from the payload.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the workspace that was linted.
        detail:       Human-readable summary of the lint report stored in details.
    """
    try:
        payload = {
            "workspace_id": workspace_id,
            "operation": "lint",
            "details": {"summary": detail},
        }
        supabase.table("teemo_wiki_log").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "wiki_service: failed to write lint log for workspace %s: %s",
            workspace_id,
            exc,
        )


def _log_wiki_operation(
    supabase: Any,
    *,
    workspace_id: str,
    document_id: str,
    pages_created: int,
    status: str,
    detail: str,
) -> None:
    """Insert a log entry into teemo_wiki_log.

    Logs the outcome of an ingest or re-ingest operation for observability.
    ``created_at`` is managed by the DB default — omitted from the payload.

    Args:
        supabase:      Authenticated Supabase client.
        workspace_id:  UUID of the workspace.
        document_id:   UUID of the document that was ingested.
        pages_created: Number of wiki pages created or upserted.
        status:        Outcome — "synced", "error", etc.
        detail:        Human-readable detail string (error message or summary).
    """
    try:
        payload = {
            "workspace_id": workspace_id,
            "document_id": document_id,
            "pages_created": pages_created,
            "status": status,
            "detail": detail,
        }
        supabase.table("teemo_wiki_log").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        # Log failures must not cascade — wiki ingest should still succeed/fail
        # based on the main operation, not on the logging side effect.
        logger.warning(
            "wiki_service: failed to write wiki log for document %s: %s",
            document_id,
            exc,
        )
