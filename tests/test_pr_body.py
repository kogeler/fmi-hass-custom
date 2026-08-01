# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for changelog-managed pull-request bodies."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PR_BODY_SCRIPT = ROOT / ".github" / "scripts" / "pr_body.py"
WORKFLOW = ROOT / ".github" / "workflows" / "pr-body.yml"
START_MARKER = "<!-- fmi-changelog:start -->"
END_MARKER = "<!-- fmi-changelog:end -->"


def _run(
    tmp_path: Path,
    *,
    changelog: str,
    existing_body: str = "",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the production helper against isolated input files."""
    changelog_path = tmp_path / "CHANGELOG.md"
    existing_path = tmp_path / "existing.md"
    output_path = tmp_path / "updated.md"
    changelog_path.write_text(changelog, encoding="utf-8")
    existing_path.write_text(existing_body, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(PR_BODY_SCRIPT),
            "--changelog",
            str(changelog_path),
            "--existing-body",
            str(existing_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result, output_path


def test_uses_first_unreleased_section_and_preserves_manual_text(tmp_path: Path) -> None:
    """The top changelog section is appended without older release content."""
    result, output = _run(
        tmp_path,
        changelog=(
            "# Changelog\n\n"
            "## Unreleased\n\n### Added\n\n- New behavior.\n\n"
            "## 1.0.0 - 2026-08-01\n\n- Old behavior.\n"
        ),
        existing_body="Manual PR context.\n",
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == (
        "Manual PR context.\n\n"
        f"{START_MARKER}\n"
        "## Unreleased\n\n### Added\n\n- New behavior.\n"
        f"{END_MARKER}\n"
    )


def test_uses_first_versioned_section_when_no_unreleased_section(tmp_path: Path) -> None:
    """A release branch exposes its current dated version section verbatim."""
    result, output = _run(
        tmp_path,
        changelog=(
            "# Changelog\n\n"
            "## 1.1.0 - 2026-09-01\n\n### Fixed\n\n- Current fix.\n\n"
            "## 1.0.0 - 2026-08-01\n\n- Previous fix.\n"
        ),
    )

    assert result.returncode == 0, result.stderr
    body = output.read_text(encoding="utf-8")
    assert "## 1.1.0 - 2026-09-01" in body
    assert "- Current fix." in body
    assert "Previous fix" not in body


def test_replaces_only_existing_managed_block(tmp_path: Path) -> None:
    """Synchronization retains manual text before and after the generated block."""
    existing = (
        "Manual introduction.\n\n"
        f"{START_MARKER}\n## Old\n\n- Stale.\n{END_MARKER}\n\n"
        "Manual checklist.\n"
    )
    result, output = _run(
        tmp_path,
        changelog="# Changelog\n\n## Unreleased\n\n- Fresh.\n",
        existing_body=existing,
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == (
        "Manual introduction.\n\n"
        f"{START_MARKER}\n## Unreleased\n\n- Fresh.\n{END_MARKER}\n\n"
        "Manual checklist.\n"
    )


@pytest.mark.parametrize(
    ("changelog", "existing_body", "message"),
    [
        ("# Changelog\n", "", "level-two section"),
        ("# Changelog\n\n## Unreleased\n\nNothing yet.\n", "", "bullet entry"),
        (
            "# Changelog\n\n## Unreleased\n\n- Entry.\n",
            f"{START_MARKER}\nunterminated",
            "managed markers",
        ),
        (
            f"# Changelog\n\n## Unreleased\n\n- {START_MARKER}\n",
            "",
            "reserved marker",
        ),
    ],
)
def test_rejects_malformed_inputs(
    tmp_path: Path,
    changelog: str,
    existing_body: str,
    message: str,
) -> None:
    """Invalid source or an ambiguous managed block fails without output."""
    result, output = _run(
        tmp_path,
        changelog=changelog,
        existing_body=existing_body,
    )

    assert result.returncode == 1
    assert message in result.stderr
    assert not output.exists()


def test_rejects_body_above_github_limit(tmp_path: Path) -> None:
    """The helper fails before GitHub rejects an oversized PR body."""
    result, output = _run(
        tmp_path,
        changelog=f"# Changelog\n\n## Unreleased\n\n- {'x' * 66_000}\n",
    )

    assert result.returncode == 1
    assert "GitHub pull-request body limit" in result.stderr
    assert not output.exists()


def test_workflow_never_checks_out_or_executes_head_code() -> None:
    """The privileged metadata workflow treats the head changelog only as data."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "pull-requests: write" in workflow
    assert "github.rest.repos.getContent" in workflow
    assert workflow.count("github.rest.pulls.get") == 2
    assert "github.rest.pulls.update" in workflow
    assert "python .github/scripts/pr_body.py" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in workflow
    assert "repository: ${{ github.event.pull_request.head.repo" not in workflow
    assert "allow-unsafe-pr-checkout" not in workflow
    assert "git fetch" not in workflow
    assert "pip install" not in workflow
    assert "secrets." not in workflow
