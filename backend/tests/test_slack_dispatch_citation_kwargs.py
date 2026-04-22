"""Tests for _final_update_kwargs — the branching point that decides whether
the dispatcher's final chat_update carries a Block Kit ``blocks=`` payload
or a plain ``text=`` fallback (STORY-017-09).

Full _stream_agent_to_slack coverage would require a live pydantic-ai
Agent + AsyncWebClient fake; pinning the branching logic in isolation is
enough to lock the contract without that plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.citation_collector import Citation
from app.services.slack_dispatch import _final_update_kwargs


@dataclass
class FakeDeps:
    """Stand-in for AgentDeps — only the .citations attribute is read by
    the helper, so a minimal fake is sufficient."""

    citations: list = field(default_factory=list)


def test_no_citations_returns_text_only() -> None:
    kwargs = _final_update_kwargs("hello world", FakeDeps())
    assert kwargs == {"text": "hello world"}
    assert "blocks" not in kwargs


def test_citations_present_adds_blocks_and_keeps_text() -> None:
    deps = FakeDeps(
        citations=[
            Citation(
                kind="wiki",
                title="Refund Policy",
                url="https://example.com/wiki/refund-policy",
                category="source-summary",
                source_id="wiki:refund-policy",
            )
        ]
    )
    kwargs = _final_update_kwargs("our refund window is 30 days.", deps)
    assert kwargs["text"] == "our refund window is 30 days."
    assert "blocks" in kwargs
    blocks = kwargs["blocks"]
    # Shape is covered in test_slack_blocks.py — here we only assert the
    # dispatcher propagated the list rather than building text-only.
    assert isinstance(blocks, list)
    assert blocks[0]["type"] == "section"
    assert blocks[1]["type"] == "section"
    assert blocks[1]["text"]["text"].startswith("> *Sources*")


def test_deps_without_citations_attr_falls_back_to_text() -> None:
    """Defensive: objects that don't expose .citations (e.g. older test
    fakes) should not crash the dispatcher — we treat missing as empty."""

    class DepsWithoutCitations:
        pass

    kwargs = _final_update_kwargs("hi", DepsWithoutCitations())
    assert kwargs == {"text": "hi"}
