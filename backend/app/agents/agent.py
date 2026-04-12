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
from typing import Any
from urllib.parse import urlparse

import httpx

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


def _build_system_prompt(skills: list[dict]) -> str:
    """Assemble the system prompt for the Tee-Mo agent.

    Combines a static identity preamble with an optional skill catalog
    section. The skills section is only included when the workspace has at
    least one active skill — omitting it entirely when empty prevents the LLM
    from being confused by an empty catalog header.

    Args:
        skills: List of skill dicts with ``name`` and ``summary`` keys,
                as returned by skill_service.list_skills(). May be empty.

    Returns:
        A fully assembled system prompt string.
    """
    preamble = (
        "You are Tee-Mo, an AI assistant embedded in your team's Slack workspace.\n"
        "You help teams with standups, reports, analysis, and workflow automation.\n\n"
        "Rules:\n"
        "- Be concise and helpful.\n"
        "- Never reveal internal workspace IDs, API keys, or stack traces.\n"
        "- When a skill is available that fits the request, load it first with load_skill.\n"
        "- Always confirm destructive actions before executing them.\n"
        "- Always identify who you're responding to by name when the thread has multiple participants.\n\n"
        "## Tools — when to use which\n"
        "- **web_search(query)**: Search the internet for general information.\n"
        "- **crawl_page(url)**: Fetch a public web page and return its content as readable markdown. "
        "Best for reading articles, docs, and web pages.\n"
        "- **http_request(method, url, ...)**: Make raw HTTP requests to APIs. Use this when you need "
        "custom headers (e.g. Authorization tokens), non-GET methods (POST, PUT, DELETE), "
        "or need to work with structured API responses (JSON). Best for authenticated API calls, "
        "webhooks, and data retrieval from REST endpoints."
    )

    if not skills:
        return preamble

    skill_lines = "\n".join(
        f"- {s['name']}: {s['summary']}" for s in skills
    )
    skills_section = f"\n\n## Available Skills\n{skill_lines}"

    return preamble + skills_section


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
      8. Assemble system prompt with optional skill catalog.
      9. Build 4 skill tool functions (load_skill, create_skill, update_skill, delete_skill).
      10. Construct and return (Agent, AgentDeps).

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

    # --- 8. Build system prompt ---
    prompt = _build_system_prompt(skills)

    # --- 9. Build skill tool functions ---
    # Tools are defined as closures capturing (workspace_id, supabase) from
    # the factory's scope. pydantic-ai will introspect the function signature
    # to determine parameter names when the LLM calls them.

    async def load_skill(ctx: Any, skill_name: str) -> str:
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
        ctx: Any,
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
        ctx: Any,
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

    async def delete_skill(ctx: Any, skill_name: str) -> str:
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

    async def web_search(ctx: Any, query: str) -> str:
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

    async def crawl_page(ctx: Any, url: str) -> str:
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
        ctx: Any,
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

    # --- 12. Construct Agent and deps ---
    agent = Agent(
        model,
        system_prompt=prompt,
        deps_type=AgentDeps,
        tools=[load_skill, create_skill, update_skill, delete_skill, web_search, crawl_page, http_request],
    )
    deps = AgentDeps(
        workspace_id=workspace_id,
        supabase=supabase,
        user_id=user_id,
    )

    return (agent, deps)
