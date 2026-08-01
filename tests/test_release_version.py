# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for the CI release-version contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
VERSION_SCRIPT = ROOT / ".github" / "scripts" / "version.py"


def _write_repository(
    root: Path,
    *,
    version: str = "1.0.0",
    manifest_version: str = "1.0.0",
    changelog: str | None = None,
) -> None:
    """Create the version-bearing portion of a test repository."""
    integration = root / "custom_components" / "fmi"
    integration.mkdir(parents=True)
    (root / ".version").write_text(f"{version}\n", encoding="utf-8")
    (integration / "manifest.json").write_text(
        json.dumps({"domain": "fmi", "version": manifest_version}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        changelog or "# Changelog\n\n## 1.0.0 - 2026-08-01\n\n### Added\n\n- Release entry.\n",
        encoding="utf-8",
    )


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the version helper through its production CLI."""
    return subprocess.run(
        [sys.executable, str(VERSION_SCRIPT), "--root", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("version", "message"),
    [
        ("v1.0.0", "stable X.Y.Z"),
        ("1.0", "stable X.Y.Z"),
        ("1.0.0b1", "stable X.Y.Z"),
        ("01.0.0", "stable X.Y.Z"),
    ],
)
def test_rejects_noncanonical_versions(tmp_path: Path, version: str, message: str) -> None:
    """Only stable canonical SemVer is eligible for publication."""
    _write_repository(tmp_path, version=version)

    result = _run(tmp_path, "check")

    assert result.returncode == 1
    assert message in result.stderr


def test_requires_manifest_to_match_version(tmp_path: Path) -> None:
    """The manifest is a checked generated mirror, not another version source."""
    _write_repository(tmp_path, manifest_version="0.6.2")

    result = _run(tmp_path, "check")

    assert result.returncode == 1
    assert "does not match .version 1.0.0" in result.stderr


@pytest.mark.parametrize(
    "changelog",
    [
        "# Changelog\n\n## Unreleased\n\n- Pending.\n",
        "# Changelog\n\n## 1.0.0\n\n- Missing date.\n",
        "# Changelog\n\n## 1.0.0 - 2026-08-01\n\nNo entries.\n",
    ],
)
def test_requires_matching_nonempty_changelog_section(tmp_path: Path, changelog: str) -> None:
    """A release cannot be published without curated notes for its version."""
    _write_repository(tmp_path, changelog=changelog)

    result = _run(tmp_path, "check")

    assert result.returncode == 1
    assert "CHANGELOG.md" in result.stderr


@pytest.mark.parametrize("base", ["1.0.0", "1.0.1", "2.0.0"])
def test_requires_strict_version_increment(tmp_path: Path, base: str) -> None:
    """Unchanged and decreasing versions fail before merge or release."""
    _write_repository(tmp_path)

    result = _run(tmp_path, "check", "--base-version", base)

    assert result.returncode == 1
    assert f"must be greater than base version {base}" in result.stderr


def test_accepts_strict_version_increment(tmp_path: Path) -> None:
    """A greater version with synchronized metadata is accepted."""
    _write_repository(tmp_path)

    result = _run(tmp_path, "check", "--base-version", "0.6.2")

    assert result.returncode == 0
    assert result.stdout == "1.0.0\n"


def test_sync_copies_version_to_manifest(tmp_path: Path) -> None:
    """The explicit sync command generates the committed manifest mirror."""
    _write_repository(tmp_path, manifest_version="0.6.2")

    result = _run(tmp_path, "sync")

    assert result.returncode == 0
    manifest = json.loads(
        (tmp_path / "custom_components" / "fmi" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == "1.0.0"
    assert _run(tmp_path, "sync", "--check").returncode == 0


def test_release_notes_use_only_matching_section_and_full_link(tmp_path: Path) -> None:
    """Release notes contain current entries and a tag-stable full-changelog link."""
    _write_repository(
        tmp_path,
        changelog=(
            "# Changelog\n\n"
            "## Unreleased\n\n- Future entry.\n\n"
            "## 1.0.0 - 2026-08-01\n\n### Added\n\n- Current entry.\n\n"
            "## 0.6.2 - 2025-07-24\n\n- Old entry.\n"
        ),
    )
    output = tmp_path / "release-notes.md"

    result = _run(tmp_path, "notes", "--output", str(output))

    assert result.returncode == 0
    assert output.read_text(encoding="utf-8") == (
        "### Added\n\n"
        "- Current entry.\n\n"
        "Full changelog: "
        "https://github.com/kogeler/fmi-hass-custom/blob/1.0.0/CHANGELOG.md\n"
    )


def test_repository_metadata_is_release_ready() -> None:
    """The committed repository metadata satisfies the same CI contract."""
    result = _run(ROOT, "check")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1.0.0\n"


def test_initial_version_increments_legacy_release(tmp_path: Path) -> None:
    """The first .version release reads the real root legacy manifest at v0.6.2."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "manifest.json").write_text(
        json.dumps({"domain": "fmi", "version": "0.6.2"}) + "\n",
        encoding="utf-8",
    )

    result = _run(ROOT, "check", "--base-root", str(base))

    assert result.returncode == 0, result.stderr
