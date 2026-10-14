# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for the exact GitHub dependency-submission snapshot."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).parents[1]
SNAPSHOT_SCRIPT = ROOT / ".github" / "scripts" / "dependency_snapshot.py"
LOCKS = ("requirements.txt", "requirements-dev.txt", "requirements-lint.txt")


def _run_snapshot(root: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """Run the production snapshot helper against a selected repository root."""
    return subprocess.run(
        [
            sys.executable,
            str(SNAPSHOT_SCRIPT),
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _copy_inputs(destination: Path) -> None:
    """Copy only the five authoritative dependency inputs used by the helper."""
    (destination / "tools/lint").mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")
    shutil.copy2(ROOT / "tools/lint/pyproject.toml", destination / "tools/lint/pyproject.toml")
    for lock in LOCKS:
        shutil.copy2(ROOT / lock, destination / lock)


def _dependencies(project: Path) -> list[str]:
    """Return the direct dependency array from the PEP 621 project that owns it."""
    requirements: list[str] = tomllib.loads(project.read_text(encoding="utf-8"))["project"][
        "dependencies"
    ]
    return requirements


def _owned_pins(project: Path) -> dict[str, str]:
    """Return owner versions so tests never duplicate a dependency version literal."""
    pins: dict[str, str] = {}
    for item in _dependencies(project):
        requirement = Requirement(item)
        specifiers = list(requirement.specifier)
        assert len(specifiers) == 1 and specifiers[0].operator == "==", item
        pins[canonicalize_name(requirement.name)] = specifiers[0].version
    return pins


def test_snapshot_contains_all_three_exact_lock_graphs(tmp_path: Path) -> None:
    """Runtime, development, and Ruff locks are separate complete manifests."""
    output = tmp_path / "snapshot.json"
    result = _run_snapshot(ROOT, output)

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert set(payload) == {"manifests"}
    assert set(payload["manifests"]) == set(LOCKS)

    runtime = payload["manifests"]["requirements.txt"]
    development = payload["manifests"]["requirements-dev.txt"]
    lint = payload["manifests"]["requirements-lint.txt"]
    for name, manifest in payload["manifests"].items():
        assert manifest["name"] == name
        assert manifest["file"] == {"source_location": name}
        assert manifest["resolved"]

    runtime_pins = _owned_pins(ROOT / "pyproject.toml")
    assert "xmltodict" in runtime_pins
    for name, version in runtime_pins.items():
        assert runtime["resolved"][name] == {
            "package_url": f"pkg:pypi/{name}@{version}",
            "relationship": "direct",
            "scope": "runtime",
        }
    assert runtime["resolved"]["certifi"]["relationship"] == "indirect"
    assert {item["scope"] for item in runtime["resolved"].values()} == {"runtime"}
    assert development["resolved"]["homeassistant"]["relationship"] == "direct"
    assert development["resolved"]["certifi"]["relationship"] == "indirect"
    assert {item["scope"] for item in development["resolved"].values()} == {"development"}
    lint_pins = _owned_pins(ROOT / "tools/lint/pyproject.toml")
    assert set(lint_pins) == {"ruff"}
    assert lint["resolved"] == {
        name: {
            "package_url": f"pkg:pypi/{name}@{version}",
            "relationship": "direct",
            "scope": "development",
        }
        for name, version in lint_pins.items()
    }


def test_snapshot_rejects_unrecognized_lock_content(tmp_path: Path) -> None:
    """New resolver syntax cannot silently disappear from the submitted graph."""
    _copy_inputs(tmp_path)
    runtime = tmp_path / "requirements.txt"
    runtime.write_text(runtime.read_text(encoding="utf-8") + "--index-url example.invalid\n")

    result = _run_snapshot(tmp_path, tmp_path / "snapshot.json")

    assert result.returncode == 1
    assert "unsupported lock entry" in result.stderr


def test_snapshot_rejects_missing_direct_dependency(tmp_path: Path) -> None:
    """A direct PEP 621 dependency must occur at its exact version in the lock."""
    _copy_inputs(tmp_path)
    project = tmp_path / "pyproject.toml"
    content = project.read_text(encoding="utf-8")
    owned = f'"{_dependencies(project)[-1]}"'
    assert content.count(owned) == 1
    project.write_text(content.replace(owned, '"missing-package==1.0.0"'), encoding="utf-8")

    result = _run_snapshot(tmp_path, tmp_path / "snapshot.json")

    assert result.returncode == 1
    assert "direct dependencies missing from lock: missing-package" in result.stderr


def test_snapshot_rejects_hashless_pin(tmp_path: Path) -> None:
    """The API inventory cannot be generated from a non-hash lock."""
    _copy_inputs(tmp_path)
    (pin,) = _dependencies(tmp_path / "tools/lint/pyproject.toml")
    lint = tmp_path / "requirements-lint.txt"
    lint.write_text(
        f"# This file is autogenerated by pip-compile\n{pin} \\\n    # via test\n",
        encoding="utf-8",
    )

    result = _run_snapshot(tmp_path, tmp_path / "snapshot.json")

    assert result.returncode == 1
    assert f"{pin} has no SHA-256 hash" in result.stderr
