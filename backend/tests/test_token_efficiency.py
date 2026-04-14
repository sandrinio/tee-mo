"""
Token efficiency measurement — runs scenarios and reports LLM token usage.

Uses pydantic-ai's built-in usage tracking. Measures:
- Input tokens per scenario (system prompt + history + tool results)
- Output tokens per scenario (agent response)
- Tool call count
- Time to response

Run:
    cd backend && PYTHONPATH=. python3.11 tests/test_token_efficiency.py
"""

from __future__ import annotations

import asyncio
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


async def main() -> None:
    from app.core.db import get_supabase
    from app.agents.agent import build_agent

    supabase = get_supabase()
    us = supabase.table("teemo_users").select("id").limit(1).execute()
    user_id = us.data[0]["id"]

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
