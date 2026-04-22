"""Unit tests for slack_blocks.build_reply_blocks.

Covers every Gherkin scenario from the story's §2.1 that can be exercised
without a live Slack client or pydantic-ai runtime:

- No citations → returns None (caller falls back to text= only)
- Wiki citation with URL renders a clickable rich-text link
- Document citation with Drive URL renders a clickable rich-text link
- Web citation renders a link with hostname category code span
- Missing URL falls back to a plain text element
- Dedupe collapses same source_id to one chip
- Overflow produces an italic "+N more" trailing element
- The sources panel lives inside a single rich_text_quote so Slack draws
  the native left-side border around the entire panel
"""

from __future__ import annotations

from app.services.citation_collector import Citation
from app.services.slack_blocks import build_reply_blocks


def _quote_elements(blocks: list[dict]) -> list[dict]:
    """Return the rich-text elements inside the sources rich_text_quote."""
    rt = blocks[1]
    assert rt["type"] == "rich_text"
    quote = rt["elements"][0]
    assert quote["type"] == "rich_text_quote"
    return quote["elements"]


def _element_texts(elements: list[dict]) -> list[str]:
    """Flatten rich-text elements to their raw text (for ordering assertions)."""
    return [e.get("text", "") for e in elements]


class TestBuildReplyBlocks:
    def test_no_citations_returns_none(self) -> None:
        assert build_reply_blocks("hello", []) is None

    def test_reply_section_is_untouched_mrkdwn(self) -> None:
        c = Citation(kind="wiki", title="T", url=None, category=None, source_id="s")
        blocks = build_reply_blocks("our refund window is 30 days.", [c])
        assert blocks is not None
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"] == {
            "type": "mrkdwn",
            "text": "our refund window is 30 days.",
        }

    def test_quote_starts_with_bold_sources_header(self) -> None:
        c = Citation(kind="wiki", title="T", url=None, category=None, source_id="s")
        blocks = build_reply_blocks("r", [c])
        assert blocks is not None
        elements = _quote_elements(blocks)
        assert elements[0] == {
            "type": "text",
            "text": "Sources",
            "style": {"bold": True},
        }

    def test_wiki_citation_with_url_renders_link(self) -> None:
        c = Citation(
            kind="wiki",
            title="Refund Policy",
            url="https://teemo.soula.ge/app/workspaces/ws/wiki/refund-policy",
            category="source-summary",
            source_id="wiki:refund-policy",
        )
        blocks = build_reply_blocks("our refund window is 30 days.", [c])
        assert blocks is not None
        elements = _quote_elements(blocks)
        # Expect: [bold Sources, \n, link, "  ", code category]
        assert {
            "type": "link",
            "url": "https://teemo.soula.ge/app/workspaces/ws/wiki/refund-policy",
            "text": "Refund Policy",
        } in elements
        assert {
            "type": "text",
            "text": "source-summary",
            "style": {"code": True},
        } in elements

    def test_document_citation_with_drive_link(self) -> None:
        c = Citation(
            kind="document",
            title="Refund Policy.docx",
            url="https://drive.google.com/file/d/abc/view",
            category="google_drive",
            source_id="doc-abc",
        )
        blocks = build_reply_blocks("see attached", [c])
        assert blocks is not None
        elements = _quote_elements(blocks)
        assert any(
            e.get("type") == "link"
            and e.get("url") == "https://drive.google.com/file/d/abc/view"
            and e.get("text") == "Refund Policy.docx"
            for e in elements
        )
        assert any(
            e.get("style") == {"code": True} and e.get("text") == "google_drive"
            for e in elements
        )

    def test_web_citation_renders_hostname_category(self) -> None:
        c = Citation(
            kind="web",
            title="Stripe Docs",
            url="https://stripe.com/docs/refunds",
            category="stripe.com",
            source_id="https://stripe.com/docs/refunds",
        )
        blocks = build_reply_blocks("per Stripe...", [c])
        assert blocks is not None
        elements = _quote_elements(blocks)
        assert any(
            e.get("type") == "link" and e.get("url") == "https://stripe.com/docs/refunds"
            for e in elements
        )
        assert any(
            e.get("text") == "stripe.com" and e.get("style") == {"code": True}
            for e in elements
        )

    def test_missing_url_falls_back_to_plain_text(self) -> None:
        c = Citation(
            kind="wiki",
            title="Refund Policy",
            url=None,
            category=None,
            source_id="wiki:refund-policy",
        )
        blocks = build_reply_blocks("hi", [c])
        assert blocks is not None
        elements = _quote_elements(blocks)
        # No link element anywhere
        assert not any(e.get("type") == "link" for e in elements)
        # Title present as plain text
        assert {"type": "text", "text": "Refund Policy"} in elements
        # No code-style category span
        assert not any(e.get("style") == {"code": True} for e in elements)

    def test_dedupe_collapses_same_source_id(self) -> None:
        c1 = Citation(kind="document", title="Doc", url="u", category=None, source_id="doc-1")
        c2 = Citation(kind="document", title="Doc again", url="u2", category=None, source_id="doc-1")
        blocks = build_reply_blocks("reply", [c1, c2])
        assert blocks is not None
        elements = _quote_elements(blocks)
        # First occurrence wins
        titles = [e.get("text") for e in elements if e.get("type") == "link"]
        assert titles == ["Doc"]

    def test_overflow_renders_italic_plus_n_more(self) -> None:
        cs = [
            Citation(
                kind="web",
                title=f"Src {i}",
                url=f"https://example.com/{i}",
                category=None,
                source_id=f"s{i}",
            )
            for i in range(8)
        ]
        blocks = build_reply_blocks("reply", cs)
        assert blocks is not None
        elements = _quote_elements(blocks)
        links = [e for e in elements if e.get("type") == "link"]
        assert len(links) == 5  # capped at MAX_DISPLAYED_SOURCES
        assert {
            "type": "text",
            "text": "+3 more",
            "style": {"italic": True},
        } in elements

    def test_overall_structure_is_section_then_rich_text_quote(self) -> None:
        c = Citation(kind="wiki", title="T", url="https://x", category="concept", source_id="s")
        blocks = build_reply_blocks("r", [c])
        assert blocks is not None
        assert [b["type"] for b in blocks] == ["section", "rich_text"]
        assert blocks[1]["elements"][0]["type"] == "rich_text_quote"
