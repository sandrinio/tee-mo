"""
Token efficiency + extraction benchmark — runs scenarios and reports:
- LLM token usage (input/output/total per scenario)
- Tool call count and response time
- Drive extraction: time-to-extract per file and MIME type
- Extraction quality: content richness, structure, truncation, density

Run:
    cd backend && PYTHONPATH=. python3.11 tests/test_token_efficiency.py
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

WORKSPACE_ID = "34e66eea-aad6-47a0-9895-75cd0ce3caa0"


def _extract_tool_calls(result) -> list[str]:
    tools = []
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "tool_name"):
                    tools.append(part.tool_name)
    return tools


async def measure_scenario(agent, deps, name: str, prompt: str) -> dict:
    """Run a scenario and return token usage stats."""
    t0 = time.monotonic()
    result = await agent.run(prompt, deps=deps)
    elapsed = time.monotonic() - t0

    usage = result.usage()
    tools = _extract_tool_calls(result)

    return {
        "name": name,
        "prompt": prompt[:60],
        "elapsed_s": elapsed,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "requests": usage.requests,
        "tool_calls": len(tools),
        "tools": tools,
    }


def _score_extraction(content: str, mime_type: str) -> dict:
    """Compute quality signals for extracted text."""
    chars = len(content)
    truncated = content.endswith("[Content truncated at 50000 characters]")
    non_ws = sum(1 for c in content if not c.isspace())
    density = non_ws / chars if chars else 0.0
    tables = len(re.findall(r"^\|[ -]+\|", content, re.MULTILINE))
    headers = len(re.findall(r"^#{1,6} ", content, re.MULTILINE))
    words = re.findall(r"\b\w{3,}\b", content.lower())
    vocab = len(set(words))
    tokens_est = chars // 4

    # Quality verdict
    if chars < 100:
        verdict = "EMPTY/SCANNED"
    elif density < 0.4:
        verdict = "SPARSE"
    elif truncated:
        verdict = "TRUNCATED"
    else:
        verdict = "OK"

    # Structural expectations by MIME
    sheet_mimes = {
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    has_expected_structure = (
        (mime_type in sheet_mimes and tables > 0)
        or (mime_type not in sheet_mimes and (headers > 0 or chars > 500))
    )

    return {
        "chars": chars,
        "tokens_est": tokens_est,
        "truncated": truncated,
        "tables": tables,
        "headers": headers,
        "vocab": vocab,
        "density": density,
        "verdict": verdict,
        "structure_ok": has_expected_structure,
    }


_REFUSAL_PATTERNS = re.compile(
    r"don'?t have|do not have|no information|cannot find|not aware|don'?t know"
    r"|not (able|sure)|unable to (find|locate)|no (data|details|records)",
    re.IGNORECASE,
)

_KNOWLEDGE_TOOLS = {"search_wiki", "read_wiki_page", "read_document"}

# Questions tied to the actual workspace documents.
# Each entry: (label, question, expected_keywords, is_trap)
#   is_trap=True  → agent SHOULD refuse / admit uncertainty (no KB answer)
#   is_trap=False → agent SHOULD use a knowledge tool and hit keywords
_QA_SCENARIOS = [
    (
        "V-Bounce phases",
        "What are the phases of the V-Bounce process?",
        ["phase", "planning", "execution", "bounce", "sprint", "review"],
        False,
    ),
    (
        "V-Bounce failure/escalation",
        "How does V-Bounce handle failures and escalation between phases?",
        ["fail", "escalat", "correction", "qa", "architect", "gate"],
        False,
    ),
    (
        "SDLC risks",
        "What are the main risks and process gaps identified in our SDLC analysis?",
        ["risk", "gap", "process", "blueprint", "ai", "sdlc"],
        False,
    ),
    (
        "First principles",
        "Explain the first principles thinking approach described in our knowledge base.",
        ["first", "principle", "aristotle", "assumption", "reasoning", "foundation"],
        False,
    ),
    (
        "xTract team events",
        "What are the recurring events or ceremonies for the xTract team?",
        ["xtract", "event", "meeting", "ceremony", "recurring", "standup", "sync"],
        False,
    ),
    (
        "xTract geography",
        "How is the xTract team distributed geographically?",
        ["xtract", "location", "country", "region", "distributed", "office", "remote"],
        False,
    ),
    (
        "Deloitte projects",
        "List the Deloitte projects tracked in our planning sheet.",
        ["deloitte", "project", "planning", "etp"],
        False,
    ),
    (
        "Cross-doc: methodologies",
        "What software development methodologies do we use or reference?",
        ["v-bounce", "sdlc", "agile", "sprint", "methodology"],
        False,
    ),
    (
        "Hallucination trap (budget)",
        "What is our Q4 2025 marketing budget?",
        [],
        True,
    ),
    (
        "Hallucination trap (revenue)",
        "What were our total revenues last quarter?",
        [],
        True,
    ),
]


def _score_response(response_text: str, tools_used: list[str], expected_kws: list[str], is_trap: bool) -> dict:
    """Grade a single QA response."""
    grounded = any(t in _KNOWLEDGE_TOOLS for t in tools_used)
    refused = bool(_REFUSAL_PATTERNS.search(response_text))
    chars = len(response_text)

    words_in_response = set(re.findall(r"\b\w{3,}\b", response_text.lower()))
    kw_hits = sum(1 for kw in expected_kws if any(kw in w for w in words_in_response))
    kw_ratio = kw_hits / len(expected_kws) if expected_kws else 1.0

    if is_trap:
        grade = "PASS" if refused else "FAIL(hallucinated)"
    elif grounded and kw_ratio >= 0.5:
        grade = "PASS"
    elif grounded and kw_ratio < 0.5:
        grade = "WARN(low-kw)"
    elif not grounded and refused:
        grade = "WARN(refused)"
    else:
        grade = "FAIL(ungrounded)"

    return {
        "grounded": grounded,
        "refused": refused,
        "kw_ratio": kw_ratio,
        "chars": chars,
        "grade": grade,
    }


async def simulate_qa(agent, deps) -> None:
    """Run QA simulation: ask real questions, grade the agent's responses."""
    print(f"\n{'='*95}")
    print(f"  QA SIMULATION — {len(_QA_SCENARIOS)} questions against workspace knowledge")
    print(f"{'='*95}")
    print(f"\n{'Question':<35} {'Tools':<30} {'KW':>4} {'Chars':>6} {'Time':>6}  Grade")
    print("-" * 95)

    all_scores = []
    for label, question, expected_kws, is_trap in _QA_SCENARIOS:
        try:
            t0 = time.monotonic()
            result = await agent.run(question, deps=deps)
            elapsed = time.monotonic() - t0

            response_text = result.output if hasattr(result, "output") else str(result.data)
            tools_used = _extract_tool_calls(result)

            score = _score_response(response_text, tools_used, expected_kws, is_trap)
            all_scores.append({"label": label, "elapsed": elapsed, **score})

            tools_display = ", ".join(tools_used) if tools_used else "—"
            kw_display = f"{score['kw_ratio']:.0%}" if expected_kws else "trap"
            print(
                f"  {label:<35} {tools_display:<30} {kw_display:>4} "
                f"{score['chars']:>6,} {elapsed:>5.1f}s  {score['grade']}"
            )

            # Print a short excerpt of the response for manual inspection
            excerpt = response_text.replace("\n", " ")[:120]
            print(f"    ↳ {excerpt}{'…' if len(response_text) > 120 else ''}")

        except Exception as e:
            print(f"  {label:<35} ERROR: {e}")

    # Summary
    passed = sum(1 for s in all_scores if s["grade"] == "PASS")
    warned = sum(1 for s in all_scores if s["grade"].startswith("WARN"))
    failed = sum(1 for s in all_scores if s["grade"].startswith("FAIL"))
    avg_time = sum(s["elapsed"] for s in all_scores) / len(all_scores) if all_scores else 0

    print(f"\n  Results: {passed} PASS  {warned} WARN  {failed} FAIL  "
          f"(avg {avg_time:.1f}s/question)")
    print(f"{'='*95}\n")


async def benchmark_extraction(supabase) -> None:
    """Fetch all Drive files for the workspace, time extraction, and score quality."""
    from app.services.drive_service import fetch_file_content, get_drive_client

    # Get workspace Drive credentials
    ws_row = (
        supabase.table("teemo_workspaces")
        .select("encrypted_google_refresh_token")
        .eq("id", WORKSPACE_ID)
        .single()
        .execute()
    )
    token = ws_row.data.get("encrypted_google_refresh_token")
    if not token:
        print("  No Google Drive token found for this workspace — skipping extraction benchmark.\n")
        return

    drive_client = get_drive_client(token)

    # Fetch all Drive-sourced documents in this workspace
    docs_row = (
        supabase.table("teemo_documents")
        .select("id, title, doc_type, source, external_id, sync_status, content")
        .eq("workspace_id", WORKSPACE_ID)
        .execute()
    )
    docs = docs_row.data or []
    drive_docs = [d for d in docs if d.get("source") == "google_drive" and d.get("external_id")]
    agent_docs = [d for d in docs if d.get("source") != "google_drive"]

    _MIME_BY_DOC_TYPE = {
        "google_doc":   "application/vnd.google-apps.document",
        "google_sheet": "application/vnd.google-apps.spreadsheet",
        "google_slide": "application/vnd.google-apps.presentation",
        "pdf":          "application/pdf",
        "docx":         "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx":         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    print(f"\n{'='*85}")
    print(f"  EXTRACTION BENCHMARK — {len(docs)} documents ({len(drive_docs)} Drive, {len(agent_docs)} Agent/Upload)")
    print(f"{'='*85}")
    print(f"\n{'File':<35} {'Type':<12} {'Time':>6} {'Chars':>7} {'Tok~':>6} {'Tbl':>4} {'H':>3} {'Dens':>5} {'Verdict':<14} {'Struct'}")
    print("-" * 85)

    extraction_results = []
    for doc in drive_docs:
        title = (doc["title"] or "untitled")[:34]
        doc_type = doc.get("doc_type", "unknown")
        mime = _MIME_BY_DOC_TYPE.get(doc_type)
        if not mime:
            print(f"  {title:<35} {'?':<12} (unknown doc_type={doc_type!r}, skipped)")
            continue

        try:
            t0 = time.monotonic()
            content = fetch_file_content(drive_client, doc["external_id"], mime)
            if asyncio.iscoroutine(content):
                content = await content
            elapsed = time.monotonic() - t0

            q = _score_extraction(str(content), mime)
            struct_mark = "OK" if q["structure_ok"] else "WARN"
            print(
                f"  {title:<35} {doc_type:<12} {elapsed:>5.1f}s "
                f"{q['chars']:>7,} {q['tokens_est']:>6,} "
                f"{q['tables']:>4} {q['headers']:>3} {q['density']:>4.0%} "
                f"{q['verdict']:<14} {struct_mark}"
            )
            extraction_results.append({"title": title, "doc_type": doc_type, "elapsed": elapsed, **q})
        except Exception as e:
            print(f"  {title:<35} {doc_type:<12}  ERROR: {e}")

    # Agent/upload docs — content already in DB, just score quality
    if agent_docs:
        print(f"\n  {'--- Agent/Upload docs (content from DB, no re-extraction) ---':}")
        for doc in agent_docs:
            title = (doc["title"] or "untitled")[:34]
            doc_type = doc.get("doc_type", "unknown")
            content = doc.get("content") or ""
            mime = _MIME_BY_DOC_TYPE.get(doc_type, "text/plain")
            q = _score_extraction(content, mime)
            struct_mark = "OK" if q["structure_ok"] else "WARN"
            print(
                f"  {title:<35} {doc_type:<12} {'DB':>6} "
                f"{q['chars']:>7,} {q['tokens_est']:>6,} "
                f"{q['tables']:>4} {q['headers']:>3} {q['density']:>4.0%} "
                f"{q['verdict']:<14} {struct_mark}"
            )
            extraction_results.append({"title": title, "doc_type": doc_type, "elapsed": 0, **q})

    if extraction_results:
        drive_timed = [r for r in extraction_results if r["elapsed"] > 0]
        avg_time = sum(r["elapsed"] for r in drive_timed) / len(drive_timed) if drive_timed else 0
        total_chars = sum(r["chars"] for r in extraction_results)
        issues = [r for r in extraction_results if r["verdict"] != "OK"]
        struct_warns = [r for r in extraction_results if not r["structure_ok"]]

        print(f"\n  Summary:")
        print(f"    Avg extraction time (Drive): {avg_time:.1f}s")
        print(f"    Total chars extracted:       {total_chars:,}  (~{total_chars // 4:,} tokens)")
        print(f"    Quality issues:              {len(issues)} / {len(extraction_results)} files")
        if issues:
            for r in issues:
                print(f"      - {r['title']}: {r['verdict']}")
        print(f"    Structure warnings:          {len(struct_warns)} / {len(extraction_results)} files")
        if struct_warns:
            for r in struct_warns:
                print(f"      - {r['title']} ({r['doc_type']}): no tables/headers found")
    print(f"{'='*85}\n")


async def main() -> None:
    from app.core.db import get_supabase
    from app.agents.agent import build_agent

    supabase = get_supabase()
    us = supabase.table("teemo_users").select("id").limit(1).execute()
    user_id = us.data[0]["id"]

    # ── Extraction benchmark ──
    await benchmark_extraction(supabase)

    # ── Measure system prompt size first ──
    from pydantic_ai import Agent as _A
    captured: dict = {}
    original = _A.__init__

    def new_init(self, *args, **kwargs):
        sp = kwargs.get("system_prompt")
        if sp and "prompt" not in captured:
            captured["prompt"] = sp
        original(self, *args, **kwargs)

    _A.__init__ = new_init
    try:
        agent, deps = await build_agent(WORKSPACE_ID, user_id, supabase)
    finally:
        _A.__init__ = original

    system_prompt = captured.get("prompt", "")
    print(f"{'='*75}")
    print(f"  System prompt size: {len(system_prompt):,} chars")
    # Rough token estimate: ~4 chars per token for English
    print(f"  Estimated tokens:   ~{len(system_prompt) // 4:,}")
    print(f"{'='*75}\n")

    # ── QA simulation ──
    await simulate_qa(agent, deps)

    scenarios = [
        ("List documents", "What documents do you have access to?"),
        ("V-Bounce phases", "What is the V-Bounce process and what are its phases?"),
        ("Entity lookup", "Who is Sandro Suladze?"),
        ("Project list", "List the Deloitte ETP projects by name."),
        ("Capability Q (no tools)", "What can you help me with?"),
        ("Multi-concept", "How does V-Bounce handle failures and escalation?"),
        ("Wiki health", "Run a quality check on our wiki."),
        ("Hallucination trap", "What is our Q4 2024 marketing budget?"),
    ]

    results = []
    for name, prompt in scenarios:
        print(f"Running: {name}...", end=" ", flush=True)
        try:
            r = await measure_scenario(agent, deps, name, prompt)
            results.append(r)
            print(f"{r['input_tokens']:>6} in + {r['output_tokens']:>5} out = {r['total_tokens']:>6} tokens, "
                  f"{r['requests']} req, {r['tool_calls']} tools, {r['elapsed_s']:.1f}s")
        except Exception as e:
            print(f"ERROR: {e}")

    # ── Report ──
    print(f"\n{'='*75}")
    print(f"  TOKEN USAGE SUMMARY (Phase A — after search_wiki + compact prompt)")
    print(f"{'='*75}")
    print(f"\n{'Scenario':<30} {'Input':>8} {'Output':>8} {'Total':>8} {'Req':>4} {'Tools':>6} {'Time':>6}")
    print("-" * 75)
    for r in results:
        print(
            f"{r['name']:<30} "
            f"{r['input_tokens']:>8,} "
            f"{r['output_tokens']:>8,} "
            f"{r['total_tokens']:>8,} "
            f"{r['requests']:>4} "
            f"{r['tool_calls']:>6} "
            f"{r['elapsed_s']:>5.1f}s"
        )

    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    total = sum(r["total_tokens"] for r in results)
    total_req = sum(r["requests"] for r in results)
    print("-" * 75)
    print(f"{'TOTALS':<30} {total_in:>8,} {total_out:>8,} {total:>8,} {total_req:>4}")

    # Cost estimate for Gemini 2.5 Flash (used as fallback tier for output)
    # Gemini 3 Flash Preview pricing TBD; using 2.5 Flash as rough estimate:
    # Input: $0.075/M tokens, Output: $0.30/M tokens
    # (2.5 Flash pricing; 3 Flash Preview may differ)
    cost_in = total_in * 0.075 / 1_000_000
    cost_out = total_out * 0.30 / 1_000_000
    cost_total = cost_in + cost_out
    print(f"\n  Cost estimate (Gemini 2.5 Flash rate):")
    print(f"    Input:  ${cost_in:.4f} ({total_in:,} tokens × $0.075/M)")
    print(f"    Output: ${cost_out:.4f} ({total_out:,} tokens × $0.30/M)")
    print(f"    Total:  ${cost_total:.4f} for 8 scenarios")
    print(f"    Per query avg: ${cost_total / len(results):.4f}")

    # Efficiency metrics
    avg_input = total_in / len(results)
    avg_output = total_out / len(results)
    print(f"\n  Efficiency:")
    print(f"    Avg input tokens/query:  {avg_input:,.0f}")
    print(f"    Avg output tokens/query: {avg_output:,.0f}")
    print(f"    Avg requests/query:      {total_req / len(results):.1f}")
    print(f"    System prompt overhead:  ~{len(system_prompt) // 4:,} tokens per turn")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    asyncio.run(main())
