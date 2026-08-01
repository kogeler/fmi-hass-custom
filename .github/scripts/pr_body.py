# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Build a pull-request body with a changelog-managed section."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

START_MARKER = "<!-- fmi-changelog:start -->"
END_MARKER = "<!-- fmi-changelog:end -->"
MAX_CHANGELOG_BYTES = 1_000_000
MAX_PR_BODY_BYTES = 65_536
SECTION_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


class PullRequestBodyError(ValueError):
    """Raised when changelog or PR body content is not safe to synchronize."""


def _read_text(path: Path, *, label: str, maximum_bytes: int) -> str:
    """Read bounded UTF-8 input."""
    if path.stat().st_size > maximum_bytes:
        raise PullRequestBodyError(f"{label} exceeds the supported size limit")
    return path.read_text(encoding="utf-8")


def _latest_changelog_section(changelog: str) -> str:
    """Return the first level-two changelog section, including its heading."""
    normalized = changelog.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(SECTION_HEADING.finditer(normalized))
    if not matches:
        raise PullRequestBodyError("CHANGELOG.md has no level-two section")

    match = matches[0]
    title = match.group(1).strip()
    end = matches[1].start() if len(matches) > 1 else len(normalized)
    content = normalized[match.end() : end].strip()
    if not content or re.search(r"^- ", content, re.MULTILINE) is None:
        raise PullRequestBodyError("latest CHANGELOG.md section must contain a bullet entry")

    section = f"## {title}\n\n{content}"
    if START_MARKER in section or END_MARKER in section:
        raise PullRequestBodyError("CHANGELOG.md section contains a reserved marker")
    return section


def _managed_block(section: str) -> str:
    """Wrap generated Markdown in stable hidden markers."""
    return f"{START_MARKER}\n{section}\n{END_MARKER}"


def _updated_body(existing_body: str, section: str) -> str:
    """Append or replace only the generated block in a PR body."""
    normalized = existing_body.replace("\r\n", "\n").replace("\r", "\n")
    start_count = normalized.count(START_MARKER)
    end_count = normalized.count(END_MARKER)
    if start_count != end_count or start_count > 1:
        raise PullRequestBodyError("pull-request body has invalid managed markers")

    block = _managed_block(section)
    if start_count == 0:
        parts = [normalized.strip(), block]
    else:
        start = normalized.index(START_MARKER)
        end = normalized.index(END_MARKER)
        if end < start:
            raise PullRequestBodyError("pull-request body has invalid managed markers")
        end += len(END_MARKER)
        parts = [normalized[:start].strip(), block, normalized[end:].strip()]

    updated = "\n\n".join(part for part in parts if part) + "\n"
    if len(updated.encode("utf-8")) > MAX_PR_BODY_BYTES:
        raise PullRequestBodyError("updated body exceeds the GitHub pull-request body limit")
    return updated


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changelog", type=Path, required=True)
    parser.add_argument("--existing-body", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _run(args: argparse.Namespace) -> None:
    """Generate the synchronized PR body."""
    changelog = _read_text(
        args.changelog,
        label="CHANGELOG.md",
        maximum_bytes=MAX_CHANGELOG_BYTES,
    )
    existing_body = _read_text(
        args.existing_body,
        label="pull-request body",
        maximum_bytes=MAX_PR_BODY_BYTES,
    )
    section = _latest_changelog_section(changelog)
    args.output.write_text(_updated_body(existing_body, section), encoding="utf-8")


def main() -> int:
    """Run the CLI and return a process exit status."""
    try:
        _run(_build_parser().parse_args())
    except (OSError, UnicodeError, PullRequestBodyError) as err:
        print(f"PR body error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
