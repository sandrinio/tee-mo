"""Unit tests for the Citation dataclass + dedupe_and_cap helper (STORY-017-09)."""

from __future__ import annotations

import pytest

from app.services.citation_collector import Citation, dedupe_and_cap


def _c(source_id: str, title: str | None = None, kind: str = "wiki") -> Citation:
    return Citation(
        kind=kind,  # type: ignore[arg-type]
        title=title or source_id,
        url=None,
        category=None,
        source_id=source_id,
    )


class TestCitationDataclass:
    def test_citation_is_frozen(self) -> None:
        c = _c("a")
        with pytest.raises(Exception):
            c.title = "mutated"  # type: ignore[misc]

    def test_citation_fields(self) -> None:
        c = Citation(
            kind="document",
            title="Refund Policy.docx",
            url="https://drive.google.com/file/d/abc/view",
            category="google_drive",
            source_id="doc-1",
        )
        assert c.kind == "document"
        assert c.title == "Refund Policy.docx"
        assert c.url == "https://drive.google.com/file/d/abc/view"
        assert c.category == "google_drive"
        assert c.source_id == "doc-1"


class TestDedupeAndCap:
    def test_empty_input_returns_empty_and_zero_overflow(self) -> None:
        displayed, overflow = dedupe_and_cap([])
        assert displayed == []
        assert overflow == 0

    def test_unique_under_cap_returns_all(self) -> None:
        cs = [_c("a"), _c("b"), _c("c")]
        displayed, overflow = dedupe_and_cap(cs)
        assert [c.source_id for c in displayed] == ["a", "b", "c"]
        assert overflow == 0

    def test_dedup_preserves_first_occurrence(self) -> None:
        cs = [_c("a", title="first"), _c("a", title="second"), _c("b")]
        displayed, overflow = dedupe_and_cap(cs)
        assert [c.source_id for c in displayed] == ["a", "b"]
        # First occurrence wins
        assert displayed[0].title == "first"
        assert overflow == 0

    def test_dedup_then_cap_counts_overflow_after_dedupe(self) -> None:
        # 7 distinct after dedupe; cap 5 → 2 overflow
        cs = [_c(f"s{i}") for i in range(7)] + [_c("s0"), _c("s1")]  # dupes
        displayed, overflow = dedupe_and_cap(cs, max_display=5)
        assert [c.source_id for c in displayed] == ["s0", "s1", "s2", "s3", "s4"]
        assert overflow == 2

    def test_exactly_at_cap_no_overflow(self) -> None:
        cs = [_c(f"s{i}") for i in range(5)]
        displayed, overflow = dedupe_and_cap(cs, max_display=5)
        assert len(displayed) == 5
        assert overflow == 0
