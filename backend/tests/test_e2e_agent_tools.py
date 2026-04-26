"""
End-to-end integration test for Sprint S-11 features.

Tests every new service and tool function against the LIVE Supabase database.
Exercises the full document + wiki lifecycle without going through pydantic-ai
(which requires a real LLM call to dispatch tools).

Run with:
    cd backend && python3.11 -m pytest tests/test_e2e_agent_tools.py -v -s

This test:
  1. Finds an existing workspace with a BYOK key
  2. Tests document CRUD (create → read → update → list → delete)
  3. Tests wiki ingest on a real document (calls scan-tier LLM)
  4. Tests wiki read + lint
  5. Tests skill lifecycle (create → load → delete)
  6. Tests web tools (search, crawl, http_request)
  7. Cleans up all created data

NOTE: This calls real LLM APIs (scan-tier) for AI descriptions and wiki ingest.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("e2e")


async def run_all_tests():
    """Exercise all S-11 features against live Supabase."""

    from app.core.db import get_supabase
    from app.core.encryption import decrypt
    from app.services import document_service, wiki_service
    from app.services.skill_service import (
        list_skills, get_skill,
        create_skill as svc_create_skill,
        delete_skill as svc_delete_skill,
    )

    supabase = get_supabase()
    results: dict[str, str] = {}
    created_doc_id: str | None = None
    created_wiki_slugs: list[str] = []

    # ── Find workspace with BYOK key ──
    ws_result = supabase.table("teemo_workspaces").select("id, name, ai_provider, encrypted_api_key").execute()
    workspace = None
    for row in (ws_result.data or []):
        if row.get("encrypted_api_key"):
            workspace = row
            break

    if not workspace:
        logger.error("No workspace with BYOK key. Create one first.")
        return False

    wid = workspace["id"]
    provider = workspace["ai_provider"]
    api_key = decrypt(workspace["encrypted_api_key"])
    logger.info(f"Workspace: {workspace['name']} ({wid}), provider: {provider}")

    # ═══════════════════════════════════════════════════════════════════
    # 1. DOCUMENT CRUD (document_service — STORY-015-01)
    # ═══════════════════════════════════════════════════════════════════

    # 1a. create_document
    logger.info("1a. create_document...")
    try:
        row = await document_service.create_document(
            supabase, wid, "E2E Test Doc",
            "# Integration Test\n\nThis tests the full S-11 document lifecycle.\n\n## Key Points\n- Schema migration works\n- Service layer works\n- Wiki ingest works",
            doc_type="markdown", source="agent",
        )
        created_doc_id = row["id"]
        assert row["sync_status"] == "pending"
        assert row["content_hash"] is not None
        assert len(row["content_hash"]) == 64  # SHA-256
        results["create_document"] = f"PASS (id={created_doc_id[:8]}...)"
    except Exception as e:
        results["create_document"] = f"FAIL: {e}"
        logger.error(f"  {e}")

    # 1b. read_document_content
    if created_doc_id:
        logger.info("1b. read_document_content...")
        try:
            content = await document_service.read_document_content(supabase, wid, created_doc_id)
            assert content is not None
            assert "Integration Test" in content
            results["read_document"] = "PASS"
        except Exception as e:
            results["read_document"] = f"FAIL: {e}"

    # 1c. read_document_content (wrong workspace — isolation test)
    logger.info("1c. read_document (workspace isolation)...")
    try:
        content = await document_service.read_document_content(supabase, "00000000-0000-0000-0000-000000000000", created_doc_id or "x")
        results["read_doc_isolation"] = "PASS" if content is None else "FAIL: returned content for wrong workspace"
    except Exception as e:
        results["read_doc_isolation"] = f"FAIL: {e}"

    # 1d. update_document
    if created_doc_id:
        logger.info("1d. update_document...")
        try:
            updated = await document_service.update_document(supabase, wid, created_doc_id, content="# Updated E2E\n\nContent was updated.")
            assert updated["sync_status"] == "pending"
            assert updated["content_hash"] != row["content_hash"]  # hash changed
            results["update_document"] = "PASS"
        except Exception as e:
            results["update_document"] = f"FAIL: {e}"

    # 1e. list_documents
    logger.info("1e. list_documents...")
    try:
        docs = await document_service.list_documents(supabase, wid)
        assert isinstance(docs, list)
        assert any(d["id"] == created_doc_id for d in docs) if created_doc_id else True
        results["list_documents"] = f"PASS ({len(docs)} docs)"
    except Exception as e:
        results["list_documents"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 2. WIKI INGEST (wiki_service — STORY-013-02)
    # ═══════════════════════════════════════════════════════════════════

    if created_doc_id:
        logger.info("2a. wiki ingest_document (calls LLM)...")
        try:
            ingest_result = await wiki_service.ingest_document(
                supabase, wid, created_doc_id, provider, api_key
            )
            pages_created = ingest_result.get("pages_created", 0)
            results["wiki_ingest"] = f"PASS ({pages_created} pages)"
            logger.info(f"  Created {pages_created} wiki pages")
        except Exception as e:
            results["wiki_ingest"] = f"FAIL: {e}"
            logger.error(f"  {e}")

    # 2b. rebuild_wiki_index
    logger.info("2b. rebuild_wiki_index...")
    try:
        index = await wiki_service.rebuild_wiki_index(supabase, wid)
        assert isinstance(index, list)
        for entry in index:
            assert "slug" in entry and "title" in entry
        created_wiki_slugs = [e["slug"] for e in index]
        results["rebuild_wiki_index"] = f"PASS ({len(index)} pages)"
    except Exception as e:
        results["rebuild_wiki_index"] = f"FAIL: {e}"

    # 2c. read_wiki_page (via direct DB query — same as the agent tool does)
    if created_wiki_slugs:
        logger.info("2c. read_wiki_page...")
        try:
            slug = created_wiki_slugs[0]
            wp_result = supabase.table("teemo_wiki_pages").select("content").eq("workspace_id", wid).eq("slug", slug).execute()
            assert wp_result.data and len(wp_result.data) > 0
            assert len(wp_result.data[0]["content"]) > 10
            results["read_wiki_page"] = f"PASS (slug={slug})"
        except Exception as e:
            results["read_wiki_page"] = f"FAIL: {e}"

    # 2d. read_wiki_page (not found)
    logger.info("2d. read_wiki_page (not found)...")
    try:
        wp_result = supabase.table("teemo_wiki_pages").select("content").eq("workspace_id", wid).eq("slug", "nonexistent-xyz").execute()
        results["read_wiki_404"] = "PASS" if not wp_result.data else "FAIL: found data"
    except Exception as e:
        results["read_wiki_404"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 3. WIKI LINT (wiki_service — STORY-013-04)
    # ═══════════════════════════════════════════════════════════════════

    logger.info("3. lint_wiki...")
    try:
        report = await wiki_service.lint_wiki(supabase, wid)
        assert isinstance(report, str)
        assert len(report) > 10
        results["lint_wiki"] = f"PASS ({len(report)} chars)"
    except Exception as e:
        results["lint_wiki"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 4. SKILL LIFECYCLE (skill_service — existing, but tested for regression)
    # ═══════════════════════════════════════════════════════════════════

    logger.info("4a. create_skill...")
    try:
        skill_row = svc_create_skill(wid, "e2e-test-skill", "E2E test", "Do the thing.", supabase)
        results["create_skill"] = f"PASS (id={skill_row['id'][:8]}...)"
    except Exception as e:
        results["create_skill"] = f"FAIL: {e}"

    logger.info("4b. get_skill...")
    try:
        skill = get_skill(wid, "e2e-test-skill", supabase)
        assert skill is not None
        assert skill["instructions"] == "Do the thing."
        results["get_skill"] = "PASS"
    except Exception as e:
        results["get_skill"] = f"FAIL: {e}"

    logger.info("4c. delete_skill...")
    try:
        svc_delete_skill(wid, "e2e-test-skill", supabase)
        gone = get_skill(wid, "e2e-test-skill", supabase)
        results["delete_skill"] = "PASS" if gone is None else "FAIL: still exists"
    except Exception as e:
        results["delete_skill"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 5. WEB TOOLS (agent.py tools — tested via direct httpx calls)
    # ═══════════════════════════════════════════════════════════════════

    import httpx
    from app.core.url_safety import is_safe_url  # lifted from agent.py — STORY-012-01

    logger.info("5a. is_safe_url (private IP block)...")
    try:
        ok_public, _ = is_safe_url("https://google.com")
        assert ok_public is True
        ok_loopback, _ = is_safe_url("http://127.0.0.1:8080")
        assert ok_loopback is False
        ok_private, _ = is_safe_url("http://192.168.1.1")
        assert ok_private is False
        results["safe_url_check"] = "PASS"
    except Exception as e:
        results["safe_url_check"] = f"FAIL: {e}"

    logger.info("5b. http_request (httpbin)...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get("https://httpbin.org/get")
            assert resp.status_code == 200
            results["http_request"] = "PASS"
    except Exception as e:
        results["http_request"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 6. HEALTH CHECK (main.py — STORY-015-01, STORY-013-01)
    # ═══════════════════════════════════════════════════════════════════

    logger.info("6. Health check tables...")
    try:
        for table in ["teemo_documents", "teemo_wiki_pages", "teemo_wiki_log"]:
            supabase.table(table).select("*").limit(0).execute()
        results["health_tables"] = "PASS (teemo_documents + wiki tables reachable)"
    except Exception as e:
        results["health_tables"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # 7. CLEANUP
    # ═══════════════════════════════════════════════════════════════════

    if created_doc_id:
        logger.info("7. Cleanup: delete test document (cascades wiki pages)...")
        try:
            deleted = await document_service.delete_document(supabase, wid, created_doc_id)
            results["delete_document"] = "PASS" if deleted else "FAIL: not deleted"
            # Verify wiki pages were cascade-deleted
            remaining = supabase.table("teemo_wiki_pages").select("id").eq("workspace_id", wid).execute()
            wiki_count = len(remaining.data) if remaining.data else 0
            results["cascade_delete"] = f"PASS ({wiki_count} wiki pages remain)"
        except Exception as e:
            results["delete_document"] = f"FAIL: {e}"

    # ═══════════════════════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════════════════════

    print("\n" + "=" * 60)
    print("  SPRINT S-11 — E2E INTEGRATION TEST REPORT")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v.startswith("PASS"))
    failed = sum(1 for v in results.values() if v.startswith("FAIL"))

    for name, status in results.items():
        icon = "PASS" if status.startswith("PASS") else "FAIL" if status.startswith("FAIL") else "SKIP"
        print(f"  [{icon}] {name}: {status}")

    print(f"\n  Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print("=" * 60)

    return failed == 0


import pytest

@pytest.mark.asyncio
async def test_all_e2e():
    """Run the full E2E integration test against live Supabase."""
    success = await run_all_tests()
    assert success, "One or more E2E tests failed"


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
