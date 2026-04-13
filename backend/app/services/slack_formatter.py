"""
Slack mrkdwn formatter — converts LLM markdown output to Slack's mrkdwn dialect.

Slack uses its own "mrkdwn" format which differs from standard markdown:
  - Bold: *text* (not **text**)
  - Italic: _text_ (not *text*)
  - Links: <url|text> (not [text](url))
  - Headers: become bold text (Slack has no native heading support)
  - Bullets: • or - (not * which renders as bold in Slack)

Adapted from OpenClaw's SlackFormatter (STORY-017-03).
Reference: https://api.slack.com/reference/surfaces/formatting
"""

from __future__ import annotations

import re


def markdown_to_mrkdwn(content: str) -> str:
    """Convert standard markdown to Slack mrkdwn format.

    Processing order avoids regex collisions:
      1. Extract code blocks (protect from transforms)
      2. Extract bold (**text**) as placeholders
      3. Convert headers (# Title) to bold placeholders
      4. Convert italic (*text*) to _text_
      5. Convert bullet lines starting with * to •
      6. Convert links [text](url) to <url|text>
      7. Restore bold/header placeholders as *text*
      8. Restore code blocks

    Args:
        content: Markdown string from LLM output.

    Returns:
        Slack mrkdwn formatted string.
    """
    if not content:
        return ""

    # Step 1: Extract code blocks to protect from transforms.
    code_blocks: list[str] = []

    def _extract_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"\x00CODE{len(code_blocks) - 1}\x00"

    result = re.sub(r"```[\s\S]*?```", _extract_code, content)

    # Step 2: Bold (**text**) → placeholder
    bold_texts: list[str] = []

    def _extract_bold(m: re.Match) -> str:
        bold_texts.append(m.group(1))
        return f"\x00BOLD{len(bold_texts) - 1}\x00"

    result = re.sub(r"\*\*(.+?)\*\*", _extract_bold, result)

    # Step 3: Headers (# through ######) → placeholder
    header_texts: list[str] = []

    def _extract_header(m: re.Match) -> str:
        header_texts.append(m.group(1).strip())
        return f"\x00HEAD{len(header_texts) - 1}\x00"

    result = re.sub(
        r"^#{1,6}\s+(.+?)$",
        _extract_header,
        result,
        flags=re.MULTILINE,
    )

    # Step 4: Italic (*text*) → _text_
    # All ** bold and # headers are safely stored as placeholders now.
    result = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", result)

    # Step 5: Bullet lines starting with * → • (prevent Slack bold rendering)
    result = re.sub(r"^(\s*)\* ", r"\1• ", result, flags=re.MULTILINE)

    # Step 6: Links [text](url) → <url|text>
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", result)

    # Step 7: Restore bold placeholders → *text*
    for i, text in enumerate(bold_texts):
        result = result.replace(f"\x00BOLD{i}\x00", f"*{text}*")

    # Step 8: Restore header placeholders → *text*
    for i, text in enumerate(header_texts):
        result = result.replace(f"\x00HEAD{i}\x00", f"*{text}*")

    # Step 9: Restore code blocks
    for i, code in enumerate(code_blocks):
        result = result.replace(f"\x00CODE{i}\x00", code)

    return result
