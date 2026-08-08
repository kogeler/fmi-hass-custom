# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for moving Home Assistant compatibility resolution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "compatibility.py"
SPEC = importlib.util.spec_from_file_location("fmi_compatibility_helper", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
COMPATIBILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPATIBILITY)


def test_missing_prerelease_is_an_informational_skip(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Do not report a failed job when no prerelease candidate exists."""

    def unavailable(**_: object) -> None:
        raise COMPATIBILITY.CompatibilityUnavailable("no prerelease candidate")

    monkeypatch.setattr(COMPATIBILITY, "_resolve", unavailable)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "prerelease",
            "--bootstrap",
            str(tmp_path / "bootstrap.txt"),
            "--homeassistant",
            str(tmp_path / "homeassistant.txt"),
            "--direct",
            str(tmp_path / "direct.txt"),
            "--output",
            str(tmp_path / "resolved.txt"),
        ],
    )

    assert COMPATIBILITY.main() == 0
    assert "Informational compatibility check skipped" in capsys.readouterr().out


def test_recreated_prerelease_must_still_match_the_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a stable result fatal after a prerelease graph was selected."""
    monkeypatch.setattr(COMPATIBILITY, "_distribution_version", lambda *_: "current")

    with pytest.raises(COMPATIBILITY.CompatibilityUnavailable):
        COMPATIBILITY._assert_channel("python", "prerelease", allow_unavailable=True)

    with pytest.raises(COMPATIBILITY.CompatibilityError):
        COMPATIBILITY._assert_channel("python", "prerelease")
