"""
Tee-Mo agent factory — STORY-007-02.

Provides build_agent(), a factory that constructs a fully configured
pydantic-ai Agent for a workspace using BYOK (Bring Your Own Key)
provider configuration.

Design decisions:
  - Module-level globals (Agent, GoogleModel, etc.) start as None and are
    populated by _ensure_model_imports() on first call. This allows tests to
    monkeypatch module-level names BEFORE the lazy import runs — if the name
    is already non-None when _ensure_model_imports runs, the real import is
    skipped and the mock stays in place.
  - No FastAPI imports. This module is isolated from the HTTP layer; the
    Slack dispatch service bridges the two (S-07 sprint rule).
  - All Supabase access uses the supabase client passed in as an argument —
    no get_supabase() call inside this module (the caller provides the client).
  - Encryption is delegated to app.core.encryption.decrypt — never call
    AESGCM directly (FLASHCARDS.md S-05 rule).
  - Skills are fetched via app.services.skill_service.list_skills at Agent
    construction time. The L1 catalog (name + summary) is injected into the
    system prompt; full instructions are loaded at runtime via the load_skill tool.

Module isolation (enforced by sprint rule):
  MUST NOT import anything from fastapi. No Request, no Depends, no APIRouter.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from pydantic_ai import RunContext

from app.services import document_service as _doc_service
from app.services import wiki_service as _wiki_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IP safety — block requests to private/internal networks
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS = [
    ipaddress.ip_network(cidr)
    for cidr in [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fd00::/8",
        "fe80::/10",
    ]
]


def _is_safe_url(url: str) -> bool:
    """Check that a URL does not resolve to a private/internal IP address.

    Resolves the hostname via DNS first, then checks all returned addresses
    against the blocked CIDR list. This prevents DNS rebinding attacks where
    a hostname initially resolves to a public IP but later resolves to an
    internal one.

    Args:
        url: Fully-qualified URL to check.

    Returns:
        True if all resolved IPs are public, False otherwise.
    """
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        if any(ip in net for net in _BLOCKED_NETWORKS):
            return False
    return True


# ---------------------------------------------------------------------------
# Module-level globals — populated lazily by _ensure_model_imports()
#
# Tests patch these names before calling build_agent() or _build_pydantic_ai_model()
# to replace real pydantic-ai classes with Mocks without triggering actual
# pydantic-ai extra imports (which may not be installed in the test environment).
# ---------------------------------------------------------------------------

Agent = None
GoogleModel = None
GoogleProvider = None
AnthropicModel = None
AnthropicProvider = None
OpenAIChatModel = None
OpenAIProvider = None


# ---------------------------------------------------------------------------
# Dependency container
# ---------------------------------------------------------------------------


@dataclass
class AgentDeps:
    """Dependency container injected into every pydantic-ai tool call.

    Holds the runtime context that agent tools need to access the database
    and enforce workspace isolation. workspace_id and user_id are sourced
    from the authenticated request and are NEVER derived from user or AI
    input.

    Attributes:
        workspace_id: String UUID of the workspace making the request.
        supabase:     Supabase service-role client for direct DB access.
        user_id:      String UUID of the authenticated user.
    """

    workspace_id: str
    supabase: Any
    user_id: str


# ---------------------------------------------------------------------------
# Lazy import helper
# ---------------------------------------------------------------------------


def _ensure_model_imports(provider: str) -> None:
    """Lazily import pydantic-ai classes for the given provider into module scope.

    Only imports the classes needed for the specified provider, preventing
    ImportError when a pydantic-ai optional extra is not installed.

    The module-level globals are None at load time. If a test has already
    patched them (monkeypatch.setattr), the ``if X is None`` guards will
    skip the real import and keep the mock in place.

    Args:
        provider: One of "google", "anthropic", "openai".

    Raises:
        ImportError: If the pydantic-ai extra for the given provider is not installed.
    """
    global Agent, GoogleModel, GoogleProvider
    global AnthropicModel, AnthropicProvider
    global OpenAIChatModel, OpenAIProvider

    # Agent is always needed regardless of provider
    if Agent is None:
        from pydantic_ai import Agent as _Agent  # type: ignore[import]
        Agent = _Agent  # type: ignore[assignment]

    if provider == "google":
        if GoogleModel is None:
            from pydantic_ai.models.google import GoogleModel as _GM  # type: ignore[import]
            GoogleModel = _GM  # type: ignore[assignment]
        if GoogleProvider is None:
            from pydantic_ai.providers.google import GoogleProvider as _GP  # type: ignore[import]
            GoogleProvider = _GP  # type: ignore[assignment]
    elif provider == "anthropic":
        if AnthropicModel is None:
            from pydantic_ai.models.anthropic import AnthropicModel as _AM  # type: ignore[import]
            AnthropicModel = _AM  # type: ignore[assignment]
        if AnthropicProvider is None:
            from pydantic_ai.providers.anthropic import AnthropicProvider as _AP  # type: ignore[import]
            AnthropicProvider = _AP  # type: ignore[assignment]
    elif provider == "openai":
        if OpenAIChatModel is None:
            from pydantic_ai.models.openai import OpenAIChatModel as _OM  # type: ignore[import]
            OpenAIChatModel = _OM  # type: ignore[assignment]
        if OpenAIProvider is None:
            from pydantic_ai.providers.openai import OpenAIProvider as _OP  # type: ignore[import]
            OpenAIProvider = _OP  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Model builder
# ---------------------------------------------------------------------------


def _build_pydantic_ai_model(model_id: str, provider: str, api_key: str) -> Any:
    """Instantiate a pydantic-ai model object for the given provider.

    Dispatches to the correct (ModelClass, ProviderClass) pair based on the
    provider slug. All classes are read from module-level globals populated by
    _ensure_model_imports() — or patched by tests before calling this function.

    Args:
        model_id:  Backend model identifier (e.g. "gpt-4o", "gemini-2.5-flash").
        provider:  Provider slug (e.g. "openai", "google", "anthropic").
        api_key:   Decrypted plaintext BYOK API key.

    Returns:
        A configured pydantic-ai Model instance ready to pass to Agent().

    Raises:
        ValueError: If the provider slug is not one of google, anthropic, openai.
    """
    if provider == "google":
        provider_instance = GoogleProvider(api_key=api_key)
        return GoogleModel(model_id, provider=provider_instance)
    elif provider == "anthropic":
        provider_instance = AnthropicProvider(api_key=api_key)
        return AnthropicModel(model_id, provider=provider_instance)
    elif provider == "openai":
        provider_instance = OpenAIProvider(api_key=api_key)
        return OpenAIChatModel(model_id, provider=provider_instance)
    else:
        raise ValueError(
            f"Unsupported provider: {provider!r}. "
            f"Supported providers: google, anthropic, openai"
        )


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _build_system_prompt(
    skills: list[dict],
    documents: list[dict] | None = None,
    wiki_pages: list[dict] | None = None,
) -> str:
    """Assemble the system prompt for the Tee-Mo agent.

    Combines a static identity preamble with an optional skill catalog section,
    an optional wiki index section, and an optional document catalog section.
    Sections are only included when the workspace has relevant data — omitting
    empty sections prevents the LLM from being confused by empty catalog headers.

    Updated in STORY-015-03 to use ``teemo_documents`` (UUID-based) instead of
    the legacy ``teemo_knowledge_index``. The document catalog section is titled
    ``## Available Documents``.

    Updated in STORY-013-01 to add wiki index support. When ``wiki_pages`` is
    non-empty, a ``## Wiki Index`` section is rendered above the document
    catalog. Use ``read_wiki_page(slug)`` to retrieve full page content.

    Wiki index logic (STORY-013-01 R3):
      - When ``wiki_pages`` is non-empty: render ``## Wiki Index`` with one
        entry per page in ``[{slug}] {title} — {tldr}`` format. Wiki pages
        provide structured, AI-synthesized knowledge and should be the primary
        answer source.
      - ``## Available Documents`` is rendered as an ADDITIONAL section
        alongside the wiki index, providing fallback access for exact quotes
        and data points not covered by wiki pages.
      - When ``wiki_pages`` is empty/None and ``documents`` is non-empty:
        only ``## Available Documents`` appears (transitional behavior before
        wiki ingest runs).

    Args:
        skills:     List of skill dicts with ``name`` and ``summary`` keys,
                    as returned by skill_service.list_skills(). May be empty.
        documents:  Optional list of document dicts with ``id``, ``title``,
                    ``ai_description``, and ``sync_status`` keys, as returned
                    from teemo_documents. Non-synced docs are annotated with a
                    ⏳ marker so the agent does not quote their raw content
                    before wiki ingest lands. May be None or empty.
        wiki_pages: Optional list of wiki page dicts with ``slug``, ``title``,
                    and ``tldr`` keys, as returned from teemo_wiki_pages. When
                    non-empty, the wiki index section is rendered above the
                    document catalog.

    Returns:
        A fully assembled system prompt string.
    """
    # Inject current UTC date/time so the agent has a temporal anchor for
    # "today", "this week", "recent", etc. Computed fresh on each build (build
    # is per-message, not per-process), so there's no staleness window worth
    # caching around. UTC only for now — workspace-local tz can be layered in
    # once we pass sender tz through from slack_dispatch.
    now = datetime.now(timezone.utc)
    current_time_line = (
        f"Current date: {now.strftime('%A, %Y-%m-%d')} "
        f"(UTC time {now.strftime('%H:%M')}). "
        "Use this whenever the user references 'today', 'this week', 'recent', "
        "or any other relative date — do not guess.\n\n"
    )
    preamble = (
        current_time_line
        + "You are Tee-Mo, an AI assistant embedded in your team's Slack workspace.\n"
        "You help teams with standups, reports, analysis, and workflow automation.\n\n"
        "Rules:\n"
        "- Be concise and helpful.\n"
        "- Never reveal internal workspace IDs, API keys, or stack traces.\n"
        "- When a skill is available that fits the request, load it first with load_skill.\n"
        "- Always confirm destructive actions before executing them.\n"
        "- Always identify who you're responding to by name when the thread has multiple participants.\n"
        "- CRITICAL: When users ask what documents or wiki pages are available, "
        "ONLY list items from the ## Available Documents and ## Wiki Index sections below. "
        "NEVER invent, fabricate, or guess document titles, IDs, or slugs. "
        "If no documents/wiki pages exist in the catalog, say so directly.\n"
        "- CRITICAL: When listing people, projects, or other items from a source, "
        "include ONLY names you literally read in a tool result. Do not add summary "
        "buckets like \"Other team members\", \"India\", or \"etc.\". If a section "
        "has no verified entries, omit it entirely.\n\n"
        "Output formatting:\n"
        "Write standard Markdown — **bold**, _italic_, `inline code`, ```fenced``` code "
        "blocks, `-` or `*` bullets, `[text](url)` links, `> blockquote`. The backend "
        "converts Markdown to Slack's mrkdwn before posting, so do NOT try to write "
        "Slack's native syntax (no single-asterisk bold, no `<url|text>` links, no `•` "
        "bullets). Headers (`#`, `##`) render as bold in Slack — fine to use.\n\n"
        "Tools — when to use which:\n"
        "- `web_search(query)`: Search the internet for general information.\n"
        "- `crawl_page(url)`: Fetch a public web page and return its content as readable text. "
        "Best for reading articles, docs, and web pages.\n"
        "- `http_request(method, url, ...)`: Make raw HTTP requests to APIs. Use this when you need "
        "custom headers (e.g. Authorization tokens), non-GET methods (POST, PUT, DELETE), "
        "or need to work with structured API responses (JSON). Best for authenticated API calls, "
        "webhooks, and data retrieval from REST endpoints.\n"
        "- `search_wiki(query, top_k)`: Full-text search across wiki pages. "
        "Use this FIRST when the user asks about a topic — it returns the most relevant "
        "pages ranked by BM25. Do not guess slugs; search for them.\n"
        "- `read_wiki_page(slug)`: Retrieve the full content of a wiki page by its slug. "
        "Use this AFTER search_wiki to read the most relevant pages.\n\n"
        "Knowledge-routing strategy (follow this to answer efficiently):\n"
        "1. For broad questions (\"list X\", \"overview of Y\", \"what projects do we have\"): "
        "read the matching `source-summary` page first. One summary page usually has the full "
        "list — no need to read individual entity pages.\n"
        "2. For specific facts about one thing: read one entity or concept page directly.\n"
        "3. For comparisons or synthesis: read 2-3 relevant pages, then synthesize.\n"
        "4. STOP after at most 2 search_wiki calls with no relevant results — tell the user the "
        "information isn't in the workspace rather than searching indefinitely.\n"
        "5. Never read more than 5 wiki pages in a single turn — pick the best ones.\n"
    )

    prompt = preamble

    if skills:
        skill_lines = "\n".join(
            f"- {s['name']}: {s['summary']}" for s in skills
        )
        prompt += f"\n\n## Available Skills\n{skill_lines}"

    if wiki_pages:
        # EPIC-017 Phase A: adaptive wiki index.
        # - Small workspaces (<=15 pages): show slug + title + trimmed TLDR inline.
        # - Large workspaces: show compact slug+title catalog and require `search_wiki`
        #   for retrieval. Full TLDRs read via `read_wiki_page(slug)`.
        # This keeps the system prompt under ~8K chars regardless of wiki size
        # and prevents hallucination driven by prompt stuffing.
        def _trim(text: str, max_len: int = 120) -> str:
            text = (text or "").strip().replace("\n", " ")
            return text if len(text) <= max_len else text[: max_len - 1] + "…"

        if len(wiki_pages) <= 15:
            wiki_lines = "\n".join(
                f"- [{p['slug']}] {p['title']} — {_trim(p.get('tldr', ''))}"
                for p in wiki_pages
            )
            prompt += (
                f"\n\n## Wiki Index ({len(wiki_pages)} pages)\n{wiki_lines}"
            )
        else:
            # Compact catalog: slug + title only. TLDRs fetched via search_wiki.
            catalog_lines = "\n".join(
                f"- [{p['slug']}] {p['title']}" for p in wiki_pages
            )
            prompt += (
                f"\n\n## Wiki Index ({len(wiki_pages)} pages)\n"
                "This workspace has too many wiki pages to list fully. "
                "Use `search_wiki(query)` to find pages relevant to a user's question, "
                "then use `read_wiki_page(slug)` to read specific pages. "
                "Do NOT invent slugs — only use slugs returned by search_wiki or listed below.\n\n"
                + catalog_lines
            )

    if documents:
        def _doc_line(d: dict) -> str:
            status = d.get("sync_status")
            marker = "" if status == "synced" else f" ⏳ [{status}: wiki not ready — do not quote this doc yet]"
            desc = d.get("ai_description") or "No description available."
            return f"- [{d['id']}] \"{d['title']}\" — {desc}{marker}"

        doc_lines = "\n".join(_doc_line(d) for d in documents)
        prompt += (
            f"\n\n## Available Documents ({len(documents)} total)\n"
            "When users ask what documents are available, list these documents by title and description. "
            "Use `read_document(document_id)` to read the full content of any document.\n\n"
            + doc_lines
            + "\n\nPrefer wiki pages (`read_wiki_page`) for answering questions when available. "
            "Use `read_document` when you need exact quotes, specific data points, or the wiki "
            "doesn't cover the topic yet. For documents marked ⏳ (still indexing), tell the user "
            "the doc is being processed and ask them to retry in a minute — do NOT summarize raw "
            "content from an un-indexed doc. Only create documents when the user explicitly asks you to."
        )

    return prompt


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


async def build_agent(
    workspace_id: str,
    user_id: str,
    supabase: Any,
) -> tuple[Any, AgentDeps]:
    """Build and return a fully configured pydantic-ai Agent for a workspace.

    Performs all BYOK resolution at call time — never caches the returned Agent.
    Each call reflects the current database state (model selection, key presence,
    active skills).

    Resolution steps:
      1. Query teemo_workspaces for ai_provider, ai_model, encrypted_api_key.
      2. Raise ValueError("no_workspace") if row not found.
      3. Raise ValueError("no_key_configured") if encrypted_api_key is None.
      4. Decrypt the API key via app.core.encryption.decrypt.
      5. Lazy-import model/provider classes for the provider.
      6. Instantiate the pydantic-ai model via _build_pydantic_ai_model.
      7. Fetch active skills via skill_service.list_skills.
      7.5. Fetch wiki pages and document catalog for system prompt.
      8. Assemble system prompt with optional skill + wiki/document catalogs.
      9. Build 4 skill tool functions (load_skill, create_skill, update_skill, delete_skill).
      10. Build web tools (web_search, crawl_page, http_request).
      11.5. Build document CRUD tools (read_document, create_document, update_document, delete_document).
      11.6. Build read_wiki_page tool.
      12. Construct and return (Agent, AgentDeps).

    Args:
        workspace_id: String UUID of the requesting workspace.
        user_id:      String UUID of the authenticated user.
        supabase:     Supabase service-role client for DB access.

    Returns:
        A 2-tuple of (agent_instance, AgentDeps).

    Raises:
        ValueError: "no_workspace" if the workspace row is not found.
        ValueError: "no_key_configured" if encrypted_api_key is null.
        ValueError: If the provider slug is not supported.
    """
    from app.core.encryption import decrypt
    from app.services.skill_service import (
        list_skills,
        get_skill,
        create_skill as _create_skill,
        update_skill as _update_skill,
        delete_skill as _delete_skill,
    )

    # --- 1. Fetch workspace row ---
    result = (
        supabase.table("teemo_workspaces")
        .select("ai_provider, ai_model, encrypted_api_key")
        .eq("id", workspace_id)
        .maybe_single()
        .execute()
    )

    # --- 2. Missing workspace guard ---
    if result.data is None:
        raise ValueError("no_workspace")

    row = result.data
    provider: str = row["ai_provider"]
    model_id: str = row["ai_model"]
    encrypted_api_key: str | None = row["encrypted_api_key"]

    # --- 3. Missing key guard ---
    if encrypted_api_key is None:
        raise ValueError("no_key_configured")

    # --- 4. Decrypt key ---
    api_key = decrypt(encrypted_api_key)

    # --- 5. Lazy imports ---
    _ensure_model_imports(provider)

    # --- 6. Build model ---
    model = _build_pydantic_ai_model(model_id, provider, api_key)

    # --- 7. Fetch skills ---
    skills = list_skills(workspace_id, supabase)

    # --- 7.5. Fetch wiki pages and document catalog for system prompt ---
    # STORY-013-01 R3: Query teemo_wiki_pages first. When pages exist, the wiki
    # index is rendered in the system prompt as the primary knowledge section.
    # The document catalog (## Available Documents) is rendered alongside as
    # a fallback for exact quotes and data not yet covered by wiki pages.
    wiki_result = (
        supabase.table("teemo_wiki_pages")
        .select("slug, title, tldr")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    raw_wiki_pages = wiki_result.data
    wiki_pages: list[dict] = raw_wiki_pages if isinstance(raw_wiki_pages, list) else []

    # Query teemo_documents for the document catalog.
    # STORY-015-03: replaces legacy teemo_knowledge_index query.
    # Also pull sync_status so we can annotate not-yet-indexed docs — they have
    # content but no wiki pages, which is a known hallucination vector.
    docs_result = (
        supabase.table("teemo_documents")
        .select("id, title, ai_description, sync_status")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    # Guard against mocks or unexpected non-list data from the DB client.
    raw_docs = docs_result.data
    documents: list[dict] = raw_docs if isinstance(raw_docs, list) else []

    # --- 8. Build system prompt ---
    prompt = _build_system_prompt(skills, documents, wiki_pages)

    # --- 9. Build skill tool functions ---
    # Tools are defined as closures capturing (workspace_id, supabase) from
    # the factory's scope. pydantic-ai will introspect the function signature
    # to determine parameter names when the LLM calls them.

    async def load_skill(ctx: RunContext[AgentDeps], skill_name: str) -> str:
        """Load detailed workflow instructions for a named skill.

        Args:
            ctx:        pydantic-ai RunContext with deps.
            skill_name: Exact slug name of the skill to load.
        """
        skill = get_skill(
            ctx.deps.workspace_id,
            skill_name,
            supabase=ctx.deps.supabase,
        )
        if not skill:
            return (
                f"Skill '{skill_name}' not found. "
                "Check the Available Skills list in your system prompt for valid names."
            )
        return f"## Skill: {skill['name']}\n\n{skill['instructions']}"

    async def create_skill(
        ctx: RunContext[AgentDeps],
        name: str,
        summary: str,
        instructions: str,
    ) -> str:
        """Create a new workspace skill.

        Args:
            ctx:          pydantic-ai RunContext with deps.
            name:         Slug identifier (lowercase, hyphens).
            summary:      Short "Use when..." description. Max 160 chars.
            instructions: Full workflow instructions. Max 2000 chars.
        """
        try:
            row = _create_skill(
                workspace_id=ctx.deps.workspace_id,
                name=name,
                summary=summary,
                instructions=instructions,
                supabase=ctx.deps.supabase,
            )
            return (
                f"Skill '{name}' created successfully (id={row['id']}). "
                "It will appear in the catalog on your next message."
            )
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            logger.error("[AGENT] create_skill unexpected error: %s", exc)
            return f"Failed to create skill: {exc}"

    async def update_skill(
        ctx: RunContext[AgentDeps],
        skill_name: str,
        summary: str | None = None,
        instructions: str | None = None,
    ) -> str:
        """Update a skill's summary and/or instructions.

        Args:
            ctx:          pydantic-ai RunContext with deps.
            skill_name:   Exact slug name of the skill to update.
            summary:      Optional new summary. Max 160 chars.
            instructions: Optional new instructions. Max 2000 chars.
        """
        try:
            _update_skill(
                workspace_id=ctx.deps.workspace_id,
                name=skill_name,
                supabase=ctx.deps.supabase,
                summary=summary,
                instructions=instructions,
            )
            return f"Skill '{skill_name}' updated successfully."
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            logger.error("[AGENT] update_skill unexpected error: %s", exc)
            return f"Failed to update skill: {exc}"

    async def delete_skill(ctx: RunContext[AgentDeps], skill_name: str) -> str:
        """Delete a workspace skill by name.

        Args:
            ctx:        pydantic-ai RunContext with deps.
            skill_name: Exact slug name of the skill to delete.
        """
        try:
            _delete_skill(
                workspace_id=ctx.deps.workspace_id,
                name=skill_name,
                supabase=ctx.deps.supabase,
            )
            return f"Skill '{skill_name}' deleted successfully."
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            logger.error("[AGENT] delete_skill unexpected error: %s", exc)
            return f"Failed to delete skill: {exc}"

    # --- 10. Web search tools (SearXNG + Crawl4AI) ---

    async def web_search(ctx: RunContext[AgentDeps], query: str) -> str:
        """Search the web for information.

        Args:
            ctx:   pydantic-ai RunContext.
            query: Search query string.
        """
        from app.core.config import get_settings
        s = get_settings()
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                response = await http.get(
                    f"{s.searxng_url}/search",
                    params={"format": "json", "q": query},
                )
                data = response.json()
                results = data.get("results", [])[:5]
                if not results:
                    return "No search results found."
                lines = []
                for i, r in enumerate(results, 1):
                    lines.append(f"{i}. **{r['title']}**\n   {r['url']}\n   {r.get('content', '')}\n")
                return "\n".join(lines)
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            return f"Search service unavailable: {e}"

    async def crawl_page(ctx: RunContext[AgentDeps], url: str) -> str:
        """Fetch a web page and return its content as markdown.

        Args:
            ctx: pydantic-ai RunContext.
            url: Fully-qualified URL to crawl (e.g. "https://example.com/page").
        """
        from app.core.config import get_settings
        s = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                response = await http.post(
                    f"{s.crawl4ai_url}/md",
                    json={"url": url},
                )
                data = response.json()
                if not data.get("success", False):
                    return f"Crawl failed for {url}"
                markdown = data.get("markdown", "")
                if len(markdown) > 15_000:
                    total = len(markdown)
                    markdown = markdown[:15_000] + f"\n\n[Content truncated — {total} chars total]"
                return markdown
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            return f"Crawl service unavailable: {e}"

    # --- 11. HTTP request tool (authenticated API calls) ---

    async def http_request(
        ctx: RunContext[AgentDeps],
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> str:
        """Make an HTTP request to a public URL and return the response.

        Use this for authenticated API calls, webhooks, and REST endpoints.
        Supports custom headers (e.g. Authorization) and all HTTP methods.
        Requests to private/internal network addresses are blocked for security.

        Args:
            ctx:     pydantic-ai RunContext.
            method:  HTTP method — GET, POST, PUT, PATCH, DELETE.
            url:     Fully-qualified public URL (e.g. "https://api.github.com/repos/...").
            headers: Optional dict of HTTP headers (e.g. {"Authorization": "Bearer tok_..."}).
            body:    Optional request body string (typically JSON).
        """
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            return f"Unsupported HTTP method: {method}"

        if not _is_safe_url(url):
            return "Blocked: this URL resolves to a private/internal network address."

        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.request(
                    method,
                    url,
                    headers=headers,
                    content=body,
                )
                status_line = f"HTTP {resp.status_code} {resp.reason_phrase}\n\n"
                body_text = resp.text
                if len(body_text) > 8000:
                    body_text = body_text[:8000] + f"\n\n[Truncated — {len(resp.text)} chars total]"
                return status_line + body_text
        except httpx.TimeoutException:
            return f"Request timed out after 15 seconds: {url}"
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    # --- 11.5. Document CRUD tools (STORY-015-03) ---

    async def read_document(ctx: RunContext[AgentDeps], document_id: str) -> str:
        """Read a document from the workspace's knowledge base by UUID.

        Fetches the ``content`` column from ``teemo_documents`` using the
        document's UUID. Works for all document sources (Google Drive,
        upload, agent-created). Workspace isolation is enforced via the
        workspace_id filter in document_service.

        This tool replaces the legacy ``read_drive_file`` tool which required
        a Drive file ID and made live Drive API calls. Content is now stored in
        ``teemo_documents.content`` and served directly from the database.

        Args:
            ctx:         pydantic-ai RunContext with deps.
            document_id: UUID of the document to read (as listed in the
                         '## Available Documents' section of the system prompt).

        Returns:
            The plain text content of the document, or "Document not found."
            if no matching row exists in this workspace.
        """
        content = await _doc_service.read_document_content(
            ctx.deps.supabase,
            ctx.deps.workspace_id,
            document_id,
        )
        if content is None:
            return "Document not found."
        return content

    async def create_document(ctx: RunContext[AgentDeps], title: str, content: str) -> str:
        """Create a new markdown document in the workspace knowledge base.

        Inserts a new row into ``teemo_documents`` with ``source='agent'`` and
        ``doc_type='markdown'``. The document will be picked up by the wiki
        ingest pipeline (EPIC-013) and appear in the Available Documents catalog
        on the next agent invocation.

        Respects the 15-document-per-workspace cap enforced by the DB trigger.
        Only call this tool when the user explicitly asks to create a document.

        Args:
            ctx:     pydantic-ai RunContext with deps.
            title:   Document title (max 512 chars).
            content: Markdown content of the document.

        Returns:
            Confirmation string with the new document ID, or an error message
            if the workspace document cap is reached.
        """
        try:
            row = await _doc_service.create_document(
                supabase=ctx.deps.supabase,
                workspace_id=ctx.deps.workspace_id,
                title=title,
                content=content,
                doc_type="markdown",
                source="agent",
            )
            doc_id = row["id"]
            return (
                f"Document '{title}' created (ID: {doc_id}). "
                "It will appear in the wiki shortly."
            )
        except Exception as exc:
            exc_str = str(exc)
            if "Maximum 15 documents" in exc_str or "doc_cap" in exc_str:
                return "Maximum 15 documents per workspace reached. Delete a document before creating a new one."
            logger.error("[AGENT] create_document unexpected error: %s", exc)
            return f"Failed to create document: {exc}"

    async def update_document(ctx: RunContext[AgentDeps], document_id: str, content: str) -> str:
        """Update the content of an agent-created document.

        Only documents with ``source='agent'`` can be updated via this tool.
        Drive and upload documents are managed by the sync pipeline and cannot
        be overwritten by the agent. Updating content resets ``sync_status``
        to ``'pending'`` so the wiki pipeline re-ingests the document.

        Args:
            ctx:         pydantic-ai RunContext with deps.
            document_id: UUID of the document to update.
            content:     New markdown content to store.

        Returns:
            Success confirmation, or an error message if the document does not
            exist, is not agent-created, or the update fails.
        """
        # Source guard: only agent-created documents may be modified.
        doc_result = (
            ctx.deps.supabase.table("teemo_documents")
            .select("source")
            .eq("id", document_id)
            .eq("workspace_id", ctx.deps.workspace_id)
            .maybe_single()
            .execute()
        )
        if not doc_result or not doc_result.data:
            return "Document not found."
        if doc_result.data.get("source") != "agent":
            return "Only agent-created documents can be updated."

        try:
            await _doc_service.update_document(
                supabase=ctx.deps.supabase,
                workspace_id=ctx.deps.workspace_id,
                document_id=document_id,
                content=content,
            )
            return f"Document {document_id} updated successfully."
        except Exception as exc:
            logger.error("[AGENT] update_document unexpected error: %s", exc)
            return f"Failed to update document: {exc}"

    async def delete_document(ctx: RunContext[AgentDeps], document_id: str) -> str:
        """Delete an agent-created document from the workspace knowledge base.

        Only documents with ``source='agent'`` can be deleted via this tool.
        Drive and upload documents are managed by the sync pipeline and are
        removed when deleted from the source system.

        Args:
            ctx:         pydantic-ai RunContext with deps.
            document_id: UUID of the document to delete.

        Returns:
            Success confirmation, or an error message if the document does not
            exist or is not agent-created.
        """
        # Source guard: only agent-created documents may be deleted via this tool.
        doc_result = (
            ctx.deps.supabase.table("teemo_documents")
            .select("source")
            .eq("id", document_id)
            .eq("workspace_id", ctx.deps.workspace_id)
            .maybe_single()
            .execute()
        )
        if not doc_result or not doc_result.data:
            return "Document not found."
        if doc_result.data.get("source") != "agent":
            return "Only agent-created documents can be deleted via this tool."

        try:
            deleted = await _doc_service.delete_document(
                supabase=ctx.deps.supabase,
                workspace_id=ctx.deps.workspace_id,
                document_id=document_id,
            )
            if deleted:
                return f"Document {document_id} deleted successfully."
            return "Document not found."
        except Exception as exc:
            logger.error("[AGENT] delete_document unexpected error: %s", exc)
            return f"Failed to delete document: {exc}"

    # --- 11.6. read_wiki_page tool (STORY-013-01) ---
    async def read_wiki_page(ctx: RunContext[AgentDeps], slug: str) -> str:
        """Retrieve the full content of a wiki page by its slug.

        Queries ``teemo_wiki_pages`` for a row matching both the current
        workspace and the given slug. Returns the page's ``content`` field when
        found, or a canonical not-found message directing the agent to the Wiki
        Index in the system prompt when the slug is unknown.

        Use this tool to answer questions using the workspace's structured
        knowledge base. The available slugs are listed in the ``## Wiki Index``
        section of the system prompt (when wiki pages have been ingested).

        Wiki pages are AI-synthesized summaries of workspace documents. They
        provide curated, structured answers. For exact quotes or data not yet
        in the wiki, fall back to ``read_document`` with the document UUID.

        Args:
            ctx:  pydantic-ai RunContext with deps (workspace_id, supabase).
            slug: The wiki page slug to retrieve (e.g. ``"onboarding-process"``).

        Returns:
            The full page content string, or a not-found guidance message.
        """
        try:
            result = (
                ctx.deps.supabase.table("teemo_wiki_pages")
                .select("content")
                .eq("workspace_id", ctx.deps.workspace_id)
                .eq("slug", slug)
                .execute()
            )
            rows = result.data
            if rows and isinstance(rows, list) and len(rows) > 0:
                return rows[0]["content"]
            return (
                "Wiki page not found. "
                "Available wiki pages can be seen in the Wiki Index above."
            )
        except Exception as exc:
            logger.error("read_wiki_page failed for slug=%s: %s", slug, exc, exc_info=True)
            return f"Failed to read wiki page: {exc}"

    # --- 11.65. search_wiki tool (EPIC-017 Phase A) ---
    async def search_wiki(
        ctx: RunContext[AgentDeps],
        query: str,
        top_k: int = 10,
    ) -> str:
        """Search the workspace wiki for pages relevant to a query.

        Uses Postgres full-text search (BM25) to rank wiki pages by relevance.
        This is the PRIMARY way to find pages — use it before `read_wiki_page`
        unless you already know the exact slug from the ## Wiki Index.

        Args:
            ctx:   pydantic-ai RunContext with deps.
            query: Natural-language query (e.g., "V-Bounce process phases").
            top_k: Max pages to return (default 10).

        Returns:
            Markdown list of matching pages with slug, title, type, and TLDR.
            Empty result message if no matches.
        """
        try:
            pages = await _wiki_service.search_wiki(
                ctx.deps.supabase, ctx.deps.workspace_id, query, top_k=top_k,
            )
            if not pages:
                return f"No wiki pages found for query: {query!r}"
            lines = [f"Found {len(pages)} wiki pages for {query!r}:"]
            for p in pages:
                tldr = (p.get("tldr") or "").strip()
                lines.append(
                    f"- [{p['slug']}] ({p['page_type']}) {p['title']} — {tldr[:180]}"
                )
            lines.append(
                "\nUse `read_wiki_page(slug)` to read the full content of any page."
            )
            return "\n".join(lines)
        except Exception as exc:
            logger.error("search_wiki failed: %s", exc, exc_info=True)
            return f"Failed to search wiki: {exc}"

    # --- 11.7. lint_wiki tool (STORY-013-04) ---
    async def lint_wiki(ctx: RunContext[AgentDeps]) -> str:
        """Scan the entire workspace wiki for structural quality issues.

        Performs a pure DB scan — no LLM calls — across all wiki pages in the
        workspace and returns a markdown health report. Checks for:
          - Orphan pages (no incoming related_slugs from other pages)
          - Stale pages (source documents have sync_status='pending')
          - Documents missing wiki coverage (no source-summary page exists)
          - Low-confidence pages (confidence='low')

        The report is suitable for posting directly to Slack. Use this tool when
        the user asks to audit the workspace wiki quality, find broken or stale
        content, or check which documents still need to be ingested.

        Args:
            ctx: pydantic-ai RunContext with deps (workspace_id, supabase).

        Returns:
            A markdown-formatted ``## Wiki Health Report`` string listing counts
            and details of any quality issues found.
        """
        try:
            return await _wiki_service.lint_wiki(
                ctx.deps.supabase,
                ctx.deps.workspace_id,
            )
        except Exception as exc:
            logger.error("lint_wiki failed for workspace=%s: %s", ctx.deps.workspace_id, exc, exc_info=True)
            return f"Failed to lint wiki: {exc}"

    # --- 12. Construct Agent and deps ---
    agent = Agent(
        model,
        system_prompt=prompt,
        deps_type=AgentDeps,
        tools=[load_skill, create_skill, update_skill, delete_skill, web_search, crawl_page, http_request, read_document, create_document, update_document, delete_document, search_wiki, read_wiki_page, lint_wiki],
    )
    deps = AgentDeps(
        workspace_id=workspace_id,
        supabase=supabase,
        user_id=user_id,
    )

    return (agent, deps)
