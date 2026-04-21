"""Unit tests for slack_blocks.build_reply_blocks (STORY-017-09).

Covers every Gherkin scenario from the story's §2.1 that can be exercised
without a live Slack client or pydantic-ai runtime:

- No citations → returns None (caller falls back to text= only)
- Wiki citation with URL renders clickable chip
- Document citation with Drive URL renders clickable chip
- Web citation renders clickable chip with hostname category
- Missing URL falls back to plain-label chip
- Dedupe collapses same source_id to one chip
- Overflow produces "+N more" trailing chip
- SOURCES label appears once between reply and chips
"""

from __future__ import annotations

from app.services.citation_collector import Citation
from app.services.slack_blocks import build_reply_blocks


def _context_mrkdwn_texts(blocks: list[dict]) -> list[str]:
    """Return the mrkdwn text of every context block in order."""
    out: list[str] = []
    for b in blocks:
        if b["type"] == "context":
            for el in b["elements"]:
                if el["type"] == "mrkdwn":
                    out.append(el["text"])
    return out


class TestBuildReplyBlocks:
    def test_no_citations_returns_none(self) -> None:
        assert build_reply_blocks("hello", []) is None

    def test_wiki_citation_with_url(self) -> None:
        c = Citation(
            kind="wiki",
            title="Refund Policy",
            url="https://teemo.soula.ge/app/workspaces/ws/wiki/refund-policy",
            category="source-summary",
            source_id="wiki:refund-policy",
        )
        blocks = build_reply_blocks("our refund window is 30 days.", [c])
        assert blocks is not None
        # [0] section reply, [1] *SOURCES*, [2] chip
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["text"] == "our refund window is 30 days."
        assert blocks[1]["elements"][0]["text"] == "*SOURCES*"
        chip = blocks[2]["elements"][0]["text"]
        assert (
            "<https://teemo.soula.ge/app/workspaces/ws/wiki/refund-policy|Refund Policy>"
            in chip
        )
        assert "`source-summary`" in chip

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
        chip = blocks[2]["elements"][0]["text"]
        assert "<https://drive.google.com/file/d/abc/view|Refund Policy.docx>" in chip
        assert "`google_drive`" in chip

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
        chip = blocks[2]["elements"][0]["text"]
        assert "<https://stripe.com/docs/refunds|Stripe Docs>" in chip
        assert "`stripe.com`" in chip

    def test_missing_url_falls_back_to_plain_label(self) -> None:
        c = Citation(
            kind="wiki",
            title="Refund Policy",
            url=None,
            category=None,
            source_id="wiki:refund-policy",
        )
        blocks = build_reply_blocks("hi", [c])
        assert blocks is not None
        chip = blocks[2]["elements"][0]["text"]
        assert chip == "Refund Policy"  # no <|> link syntax, no category

    def test_dedupe_collapses_same_source_id(self) -> None:
        c1 = Citation(kind="document", title="Doc", url="u", category=None, source_id="doc-1")
        c2 = Citation(kind="document", title="Doc again", url="u2", category=None, source_id="doc-1")
        blocks = build_reply_blocks("reply", [c1, c2])
        assert blocks is not None
        # section + SOURCES + 1 chip = 3 blocks (no overflow)
        assert len(blocks) == 3
        chip = blocks[2]["elements"][0]["text"]
        # first occurrence wins
        assert "<u|Doc>" in chip

    def test_overflow_renders_plus_n_more(self) -> None:
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
        mrkdwn_contexts = _context_mrkdwn_texts(blocks)
        # *SOURCES* + 5 chips + +3 more = 7 mrkdwn contexts
        assert mrkdwn_contexts[0] == "*SOURCES*"
        assert len(mrkdwn_contexts) == 1 + 5 + 1
        assert mrkdwn_contexts[-1] == "+3 more"

    def test_sources_label_is_only_context_header(self) -> None:
        c = Citation(kind="wiki", title="T", url=None, category=None, source_id="s")
        blocks = build_reply_blocks("r", [c])
        assert blocks is not None
        mrkdwn_contexts = _context_mrkdwn_texts(blocks)
        assert mrkdwn_contexts.count("*SOURCES*") == 1
