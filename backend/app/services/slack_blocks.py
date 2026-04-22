"""Slack Block Kit payload builders.

``build_reply_blocks`` produces the Block Kit list that replaces a plain
``text=`` post when the agent cited any sources during its run. The
sources footer is rendered as a ``rich_text_quote`` inside a ``rich_text``
block — this is the officially-preferred structured approach per Slack's
docs ("rich_text is strongly preferred and allows greater flexibility").
``rich_text_quote`` renders a native left-side border around its content,
which visually anchors the Sources label, every citation chip, and the
``+N more`` overflow into one grouped panel under the reply.

Kept separate from ``slack_formatter`` so the mrkdwn converter stays a
pure string → string function; anything shaping Block Kit payloads goes
here.
"""

from __future__ import annotations

from app.services.citation_collector import Citation, dedupe_and_cap


MAX_DISPLAYED_SOURCES = 5


def _citation_elements(c: Citation) -> list[dict]:
    r"""Return the rich-text elements that render a single citation chip.

    Emits a clickable ``link`` element when the citation has a URL,
    otherwise a bare ``text`` element with the title. The optional
    ``category`` tag is appended as a monospace (``code``) span —
    visually equivalent to the previous ``\`backtick\``` mrkdwn chip.
    """
    title = c.title.strip() or "(untitled)"
    if c.url:
        chip: list[dict] = [{"type": "link", "url": c.url, "text": title}]
    else:
        chip = [{"type": "text", "text": title}]
    if c.category:
        chip.append({"type": "text", "text": "  "})
        chip.append(
            {"type": "text", "text": c.category, "style": {"code": True}}
        )
    return chip


def _build_quote_elements(
    displayed: list[Citation], overflow: int
) -> list[dict]:
    """Assemble the rich-text element list for the sources blockquote.

    Layout inside the quote:

    - Bold ``Sources`` header
    - One line per citation (link + optional monospace category)
    - Optional trailing italic ``+N more`` when the list was capped
    """
    elements: list[dict] = [
        {"type": "text", "text": "Sources", "style": {"bold": True}},
    ]
    for c in displayed:
        elements.append({"type": "text", "text": "\n"})
        elements.extend(_citation_elements(c))
    if overflow > 0:
        elements.append({"type": "text", "text": "\n"})
        elements.append(
            {
                "type": "text",
                "text": f"+{overflow} more",
                "style": {"italic": True},
            }
        )
    return elements


def build_reply_blocks(
    reply_mrkdwn: str,
    citations: list[Citation],
) -> list[dict] | None:
    """Build a Block Kit payload for an agent reply that cited sources.

    Returns:
        A list of Block Kit blocks suitable for passing to Slack's
        ``chat.postMessage`` / ``chat.update`` ``blocks=`` parameter, OR
        ``None`` when ``citations`` is empty — callers treat ``None`` as
        "fall back to the plain text=-only post path".

    Layout:

    1. ``section`` — the reply itself, mrkdwn.
    2. ``rich_text`` wrapping a single ``rich_text_quote`` that holds
       the bold ``Sources`` header, one line per displayed citation
       (clickable link + optional monospace category), and an optional
       italic ``+N more`` trailing line when the citation list exceeded
       ``MAX_DISPLAYED_SOURCES``.
    """
    if not citations:
        return None

    displayed, overflow = dedupe_and_cap(citations, max_display=MAX_DISPLAYED_SOURCES)
    if not displayed:
        return None

    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": reply_mrkdwn},
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_quote",
                    "elements": _build_quote_elements(displayed, overflow),
                }
            ],
        },
    ]
