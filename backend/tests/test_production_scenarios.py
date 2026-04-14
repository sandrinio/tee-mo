"""
Production scenario simulator — runs the real agent against production data.

Simulates incoming Slack messages by directly invoking build_agent() with the
production workspace, then running agent.run() with natural language prompts.
Uses real BYOK key, real documents, real wiki pages.

This is NOT a unit test. It runs against LIVE production Supabase and makes
real LLM API calls. Treat output as qualitative evaluation, not pass/fail.

Run:
    cd backend && python3.11 tests/test_production_scenarios.py
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

WORKSPACE_ID = "34e66eea-aad6-47a0-9895-75cd0ce3caa0"


def _extract_tool_calls(result) -> list[str]:
    """Extract tool names called during an agent run, in order."""
    tools = []
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "tool_name"):
                    tools.append(part.tool_name)
    return tools


def _extract_final_text(result) -> str:
    """Extract the last text response from the agent."""
    texts = []
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str) and len(part.content) > 20:
                    texts.append(part.content)
    return texts[-1] if texts else "(no response)"


async def run_scenario(agent, deps, name: str, prompt: str) -> None:
    """Run one conversation scenario and print the result."""
    print(f"\n{'='*75}")
    print(f"  SCENARIO: {name}")
    print(f"{'='*75}")
    print(f"USER:  {prompt}")
    try:
        result = await agent.run(prompt, deps=deps)
        tools = _extract_tool_calls(result)
        answer = _extract_final_text(result)

        print(f"TOOLS: {tools or '(none)'}")
        print(f"AGENT:\n{answer}")
    except Exception as exc:
        print(f"ERROR: {exc}")


async def main() -> None:
    from app.core.db import get_supabase
    from app.agents.agent import build_agent

    supabase = get_supabase()
    us = supabase.table("teemo_users").select("id").limit(1).execute()
    user_id = us.data[0]["id"]

    print(f"Building agent for workspace {WORKSPACE_ID[:8]}...")
    agent, deps = await build_agent(WORKSPACE_ID, user_id, supabase)
    print("Agent built. Running scenarios...")

    # ── Scenario 1: List documents (previously hallucinated) ──
    await run_scenario(
        agent, deps,
        "List documents — previously hallucinated",
        "What documents do you have access to? List them by name.",
    )

    # ── Scenario 2: Specific question that should trigger search_wiki ──
    await run_scenario(
        agent, deps,
        "Cross-doc question — should use search_wiki",
        "What is the V-Bounce process and what are its phases?",
    )

    # ── Scenario 3: Entity lookup from wiki ──
    await run_scenario(
        agent, deps,
        "Entity lookup — team member info",
        "Who is Sandro Suladze and what role does this person have?",
    )

    # ── Scenario 4: Specific data question — should use read_document fallback ──
    await run_scenario(
        agent, deps,
        "Specific data — may need read_document for exact values",
        "List the Deloitte ETP projects by name.",
    )

    # ── Scenario 5: Meta question about the agent's capabilities ──
    await run_scenario(
        agent, deps,
        "Capability question — should NOT call wiki tools",
        "What can you help me with in this workspace?",
    )

    # ── Scenario 6: Non-trivial multi-concept query ──
    await run_scenario(
        agent, deps,
        "Multi-concept — testing retrieval accuracy",
        "How does the V-Bounce process handle failures and escalation?",
    )

    # ── Scenario 7: Wiki health check ──
    await run_scenario(
        agent, deps,
        "Wiki health — should call lint_wiki",
        "Run a quality check on our wiki and tell me if anything needs attention.",
    )

    # ── Scenario 8: Hallucination trap — ask about something not in the wiki ──
    await run_scenario(
        agent, deps,
        "Hallucination trap — topic not in wiki",
        "What is our quarterly marketing budget for Q4 2024?",
    )

    print(f"\n{'='*75}")
    print("  All scenarios complete.")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    asyncio.run(main())
