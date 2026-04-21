"""Slack Block Kit payload builders (STORY-017-09).

Right now the only builder is ``build_reply_blocks``, which produces the
Block Kit list that replaces a plain ``text=`` post when the agent cited
any sources during its run. The output layout matches the UX reference
captured in the story file: a main section block with the reply, a
``*SOURCES*`` context label, and one context block per cited source
rendering as a clickable mrkdwn chip with an optional muted category
tag.

Kept separate from ``slack_formatter`` so the mrkdwn converter stays a
pure string → string function; anything shaping Block Kit payloads goes
here.
"""

from __future__ import annotations

from app.services.citation_collector import Citation, dedupe_and_cap


MAX_DISPLAYED_SOURCES = 5


def _chip_mrkdwn(citation: Citation) -> str:
    """Render a single citation as mrkdwn — clickable link + muted category.

    Chips use Slack's mrkdwn link syntax ``<url|text>`` when a URL is
    available, falling back to the title alone when not (e.g. a wiki
    citation rendered before ``FRONTEND_URL`` is configured). The
    category, when present, renders as an inline code span (``` ` ```)
    to visually separate it from the title without introducing a second
    Block Kit element per chip.
    """
    title = citation.title.strip() or "(untitled)"
    label = f"<{citation.url}|{title}>" if citation.url else title
    if citation.category:
        return f"{label}  `{citation.category}`"
    return label


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

    Layout (matches STORY-017-09 §3.3):

    1. ``section`` — the reply itself, mrkdwn.
    2. ``context`` — a single ``*SOURCES*`` label.
    3. ``context`` blocks — one per cited source chip, after dedupe-and-cap.
    4. Optional ``context`` — a trailing ``+N more`` chip when the
       citation list exceeded ``MAX_DISPLAYED_SOURCES``.
    """
    if not citations:
        return None

    displayed, overflow = dedupe_and_cap(citations, max_display=MAX_DISPLAYED_SOURCES)
    if not displayed:
        return None

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": reply_mrkdwn},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "*SOURCES*"}],
        },
    ]

    for c in displayed:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": _chip_mrkdwn(c)}],
            }
        )

    if overflow > 0:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"+{overflow} more"}],
            }
        )

    return blocks
