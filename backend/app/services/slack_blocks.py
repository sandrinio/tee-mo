"""Slack Block Kit payload builders (STORY-017-09).

Right now the only builder is ``build_reply_blocks``, which produces the
Block Kit list that replaces a plain ``text=`` post when the agent cited
any sources during its run. The sources are rendered as a single mrkdwn
blockquote section — every line prefixed with ``>`` so Slack shows the
gray vertical bar on the left that visually groups the label, all
citation chips, and any trailing ``+N more`` overflow into one unit.

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


def _sources_blockquote_mrkdwn(displayed: list[Citation], overflow: int) -> str:
    """Render the full sources panel as a single mrkdwn blockquote.

    Every line is prefixed with ``> `` so Slack draws its blockquote
    vertical bar down the entire section — label, chips, and the
    optional ``+N more`` overflow all share one visual group.
    """
    lines = ["> *Sources*"]
    for c in displayed:
        lines.append(f"> {_chip_mrkdwn(c)}")
    if overflow > 0:
        lines.append(f"> _+{overflow} more_")
    return "\n".join(lines)


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
    2. ``section`` — a single mrkdwn blockquote containing the
       ``*Sources*`` label, one chip per cited source (after
       dedupe-and-cap), and an optional ``_+N more_`` line when the
       citation list exceeded ``MAX_DISPLAYED_SOURCES``.
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
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": _sources_blockquote_mrkdwn(displayed, overflow),
            },
        },
    ]
