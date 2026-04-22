"""Unit tests for slack_blocks.build_reply_blocks.

Covers every Gherkin scenario from the story's §2.1 that can be exercised
without a live Slack client or pydantic-ai runtime:

- No citations → returns None (caller falls back to text= only)
- Wiki citation with URL renders clickable chip
- Document citation with Drive URL renders clickable chip
- Web citation renders clickable chip with hostname category
- Missing URL falls back to plain-label chip
- Dedupe collapses same source_id to one chip
- Overflow produces "+N more" trailing line
- Every sources line is prefixed with ``>`` so Slack draws the blockquote bar
"""

from __future__ import annotations

from app.services.citation_collector import Citation
from app.services.slack_blocks import build_reply_blocks


def _sources_text(blocks: list[dict]) -> str:
    """Return the mrkdwn text of the sources section block (blocks[1])."""
    return blocks[1]["text"]["text"]


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
        # [0] section reply, [1] section sources (blockquote)
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["text"] == "our refund window is 30 days."
        sources = _sources_text(blocks)
        assert sources.startswith("> *Sources*")
        assert (
            "> <https://teemo.soula.ge/app/workspaces/ws/wiki/refund-policy|Refund Policy>  `source-summary`"
            in sources
        )

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
        sources = _sources_text(blocks)
        assert (
            "> <https://drive.google.com/file/d/abc/view|Refund Policy.docx>  `google_drive`"
            in sources
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
        sources = _sources_text(blocks)
        assert "> <https://stripe.com/docs/refunds|Stripe Docs>  `stripe.com`" in sources

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
        sources = _sources_text(blocks)
        # No <|> link syntax, no backtick category — bare label on its blockquote line.
        assert "\n> Refund Policy" in "\n" + sources
        assert "<" not in sources  # no mrkdwn link syntax anywhere
        assert "`" not in sources  # no category code-span

    def test_dedupe_collapses_same_source_id(self) -> None:
        c1 = Citation(kind="document", title="Doc", url="u", category=None, source_id="doc-1")
        c2 = Citation(kind="document", title="Doc again", url="u2", category=None, source_id="doc-1")
        blocks = build_reply_blocks("reply", [c1, c2])
        assert blocks is not None
        # reply section + sources section = 2 blocks
        assert len(blocks) == 2
        sources = _sources_text(blocks)
        # first occurrence wins
        assert "<u|Doc>" in sources
        assert "Doc again" not in sources

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
        sources = _sources_text(blocks)
        lines = sources.splitlines()
        # "> *Sources*" + 5 chip lines + "> _+3 more_"
        assert lines[0] == "> *Sources*"
        assert len(lines) == 1 + 5 + 1
        assert lines[-1] == "> _+3 more_"

    def test_every_sources_line_is_blockquoted(self) -> None:
        cs = [
            Citation(
                kind="wiki",
                title=f"T{i}",
                url=f"https://x/{i}",
                category="concept",
                source_id=f"s{i}",
            )
            for i in range(3)
        ]
        blocks = build_reply_blocks("r", cs)
        assert blocks is not None
        sources = _sources_text(blocks)
        for line in sources.splitlines():
            assert line.startswith("> "), f"non-blockquoted line: {line!r}"
