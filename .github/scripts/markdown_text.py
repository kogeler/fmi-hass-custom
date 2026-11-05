# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Prepare wrapped repository Markdown for GitHub surfaces that keep line breaks."""

from __future__ import annotations

import re

BLOCK_START = re.compile(r"(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\||<!--|```)")


def unwrap_soft_breaks(markdown: str) -> str:
    """Join wrapped paragraph and list-item lines, keeping every block boundary.

    GitHub renders a single newline in pull-request and release bodies as a hard break, so text
    wrapped in CHANGELOG.md would otherwise break mid-sentence there.
    """
    lines: list[str] = []
    in_fence = False
    for line in markdown.split("\n"):
        text = line.strip()
        if text.startswith("```"):
            in_fence = not in_fence
            lines.append(line)
            continue
        previous = lines[-1].strip() if lines else ""
        if (
            not in_fence
            and text
            and previous
            and not BLOCK_START.match(text)
            and not previous.startswith(("#", "```", "|", "<!--"))
        ):
            lines[-1] = f"{lines[-1].rstrip()} {text}"
        else:
            lines.append(line)
    return "\n".join(lines)
