# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for CI topology, permissions, and container boundaries."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_REFERENCE = re.compile(
    r"^\s*uses:\s*([^@\s]+)@([0-9a-f]{40})\s+#\s+(v[0-9][^\s]*)$",
    re.MULTILINE,
)


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_workflow_set_is_minimal_event_driven_and_fully_pinned() -> None:
    """Superseded workflow files cannot survive as a second execution path."""
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    assert [path.name for path in workflows] == [
        "ci.yml",
        "dependency-submission.yml",
        "pr-body.yml",
        "release.yml",
    ]
    for path in workflows:
        content = path.read_text(encoding="utf-8")
        external_uses = [
            line for line in content.splitlines() if "uses:" in line and "uses: ./" not in line
        ]
        assert "\n  schedule:" not in content
        assert "runs-on: ubuntu-24.04" not in content
        assert len(ACTION_REFERENCE.findall(content)) == len(external_uses)
        assert content.count("uses: actions/checkout@") == content.count(
            "persist-credentials: false"
        )
        for image in re.findall(r"^\s*image:\s*(\S+)$", content, re.MULTILINE):
            assert re.fullmatch(r"\S+@sha256:[0-9a-f]{64}", image)
        assert "curl " not in content
        assert "gh api" not in content

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    validator_images = re.findall(
        r"^[A-Z][A-Z0-9_]*_IMAGE\s*:=\s*(\S+)$",
        makefile,
        re.MULTILINE,
    )
    assert len(validator_images) == 3
    assert all(re.fullmatch(r"\S+@sha256:[0-9a-f]{64}", image) for image in validator_images)


def test_ci_uses_make_rootless_podman_and_independent_image_caches() -> None:
    """The workflow invokes the same confined Make contract used locally."""
    ci = _workflow("ci.yml")
    for event in ("pull_request:", "push:", "workflow_call:", "workflow_dispatch:"):
        assert event in ci
    assert "name: CI" in ci
    assert "- master" in ci
    assert "Set up Python for Ruff" in ci
    assert "cache-dependency-path: requirements-lint.txt" in ci
    assert "run: make doctor" in ci
    assert "run: make ci" in ci
    assert "run: make live" in ci
    assert "run: make validate-hassfest" in ci
    assert "run: make validate-hacs" in ci
    assert "run: make dependency-snapshot" not in ci
    assert "run: make compatibility-stable" in ci
    assert "run: make compatibility-prerelease" in ci
    assert "PYTEST_WORKERS" not in ci
    assert "pip install" not in ci
    assert "container:" not in ci

    cache_paths = re.findall(
        r"^\s+path: (\.artifacts/images/(?:toolbox|resolver)\.tar)$",
        ci,
        re.MULTILINE,
    )
    assert len(cache_paths) == ci.count("uses: actions/cache@")
    for image in ("toolbox", "resolver"):
        assert f"steps.images.outputs.{image}" in ci
        assert f".artifacts/images/{image}.tar" in ci
        assert "${{ runner.arch }}" in ci
        assert (
            f"key: podman-${{{{ runner.os }}}}-${{{{ runner.arch }}}}-{image}-"
            f"${{{{ steps.images.outputs.{image} }}}}"
        ) in ci
    assert "make image-load-toolbox" in ci
    assert "make image-load-resolver" in ci
    assert "make image-save-toolbox" in ci
    assert "make image-save-resolver" in ci


def test_ci_preserves_hacs_security_and_compatibility_gates() -> None:
    """HACS/HA-specific checks stay visible after workflow consolidation."""
    ci = _workflow("ci.yml")
    assert "name: Bounded live FMI" in ci
    assert "live-fmi:\n" in ci
    assert (
        "needs: quality"
        in ci.split("\n  live-fmi:\n", maxsplit=1)[1].split("\n  hassfest:\n", maxsplit=1)[0]
    )
    hassfest = ci.split("\n  hassfest:\n", maxsplit=1)[1].split(
        "\n  hacs-validation:\n", maxsplit=1
    )[0]
    assert "name: Hassfest" in hassfest
    assert "needs: quality" in hassfest
    assert "run: make validator-image-hassfest" in hassfest
    assert "run: make validate-hassfest" in hassfest

    hacs = ci.split("\n  hacs-validation:\n", maxsplit=1)[1].split(
        "\n  dependency-review:\n", maxsplit=1
    )[0]
    assert "name: HACS validation" in hacs
    assert "needs: quality" in hacs
    assert "INPUT_GITHUB_TOKEN: ${{ github.token }}" in ci
    assert "github.event.pull_request.head.repo.full_name || github.repository" in ci
    assert "github.event.pull_request.head.sha || github.sha" in ci
    assert "run: make validator-image-hacs" in hacs
    assert "run: make validate-hacs" in hacs
    assert "hacs/action@" not in ci
    assert "home-assistant/actions/hassfest@" not in ci

    prerelease = ci.split("\n  compatibility-prerelease:\n", maxsplit=1)[1].split(
        "\n  version:\n", maxsplit=1
    )[0]
    assert "continue-on-error: true" in prerelease
    stable = ci.split("\n  compatibility-stable:\n", maxsplit=1)[1].split(
        "\n  compatibility-prerelease:\n", maxsplit=1
    )[0]
    assert "continue-on-error" not in stable

    assert "queries: security-extended" in ci
    assert "- actions" in ci
    assert "- python" in ci
    assert "category: .github/workflows/codeql.yml:analyze/language:${{ matrix.language }}" in ci
    assert "security-events: write" in ci
    assert "actions/dependency-review-action@" in ci
    assert "if: github.event.pull_request.head.repo.full_name == github.repository" in ci
    assert "if: github.event.pull_request.head.repo.full_name != github.repository" in ci
    assert "github.event.repository.fork" not in ci
    assert "Audit the frozen fork environment" in ci
    assert "run: make audit" in ci


def test_ci_write_permissions_are_confined_to_codeql() -> None:
    """Reusable CI cannot request the contents-write permission denied by Release."""
    ci = _workflow("ci.yml")
    assert "permissions:\n  contents: read" in ci
    assert "pull-requests: write" not in ci
    assert ci.count("security-events: write") == 1
    assert "contents: write" not in ci
    assert "$GITHUB_STEP_SUMMARY" in ci
    assert "feat/map-location" not in ci
    assert "TEMPORARY" not in ci


def test_dependency_submission_has_a_separate_trusted_write_boundary() -> None:
    """Only a direct master push can upload the three validated lock manifests."""
    submission = _workflow("dependency-submission.yml")
    for proof in (
        "name: Dependency submission",
        "push:",
        "- master",
        "name: Submit dependency graph",
        "contents: write",
        "persist-credentials: false",
        "run: make dependency-snapshot",
        "sha: context.sha",
        "POST /repos/{owner}/{repo}/dependency-graph/snapshots",
        'correlator: "fmi-hass-custom-pip-locks"',
        '"X-GitHub-Api-Version": "2026-03-10"',
        "github-token: ${{ github.token }}",
        "response.status !== 201",
        "ref: context.ref",
        'response.data.result !== "SUCCESS"',
    ):
        assert proof in submission
    assert submission.count("contents: write") == 1
    assert "pull_request:" not in submission
    assert "workflow_call:" not in submission
    assert "workflow_dispatch:" not in submission
    assert 'new Set(["SUCCESS", "ACCEPTED"])' not in submission
    assert "BOX_" not in submission


def test_version_job_compares_exact_base_and_head_through_make() -> None:
    """Version checks permit only recovery of a still-unpublished release train."""
    ci = _workflow("ci.yml")
    version = ci.split("\n  version:\n", maxsplit=1)[1]
    assert "github.event.pull_request.base.sha ||" in version
    assert "github.event.before ||" in version
    assert "inputs.base_ref" in version
    assert "github.event.pull_request.head.repo.full_name || github.repository" in version
    assert "github.event.pull_request.head.sha || github.sha" in version
    assert "github.rest.repos.getReleaseByTag" in version
    assert "github.rest.repos.getLatestRelease" in version
    assert 'latestVersion = "0.6.2"' in version
    assert 'core.setOutput("unpublished_base_version", latestVersion)' in version
    assert "current_version=\"$(tr -d '\\r\\n' < .version)\"" in version
    assert '"$current_version" == "$base_version"' in version
    assert '-n "$UNPUBLISHED_BASE_VERSION"' in version
    assert "base_version=" in version
    assert 'make version-check VERSION_ARGS="--base-version $base_version"' in version


def test_release_reuses_ci_and_writes_only_in_publish_job() -> None:
    """A new release publishes only after the exact pushed workflow gate succeeds."""
    release = _workflow("release.yml")
    state = release.split("\n  release-state:\n", maxsplit=1)[1].split("\n  ci:\n", maxsplit=1)[0]
    for proof in (
        "github.rest.repos.getContent",
        'path: ".version"',
        "ref: context.sha",
        "github.rest.repos.getReleaseByTag",
        "github.rest.git.getRef",
        "tag.data.object.type",
        "tag.data.object.sha !== existing.data.target_commitish",
        'core.setOutput("release_required", "false")',
        'core.setOutput("release_required", "true")',
    ):
        assert proof in state

    ci_gate = release.split("\n  ci:\n", maxsplit=1)[1].split("\n  publish:\n", maxsplit=1)[0]
    assert "uses: ./.github/workflows/ci.yml" in ci_gate
    assert "needs: release-state" in ci_gate
    assert "security-events: write" in ci_gate
    assert "contents: read" in ci_gate

    publish = release.split("\n  publish:\n", maxsplit=1)[1]
    assert "- release-state" in publish
    assert "- ci" in publish
    assert "contents: write" in publish
    assert "run: make release-notes" in publish
    assert "RELEASE_NOTES_PATH: .artifacts/release-notes.md" in publish
    assert release.count("contents: write") == 1


def test_pr_body_is_the_only_pull_request_target_write_boundary() -> None:
    """Untrusted head code cannot execute with the metadata write token."""
    combined = "\n".join(
        _workflow(name)
        for name in ("ci.yml", "dependency-submission.yml", "pr-body.yml", "release.yml")
    )
    pr_body = _workflow("pr-body.yml")
    assert combined.count("pull_request_target:") == 1
    assert "pull-requests: write" in pr_body
    assert "contents: write" not in pr_body
    assert "github.rest.repos.getContent" in pr_body
    assert "python .github/scripts/pr_body.py" in pr_body
    assert "repository: ${{ github.event.pull_request.head.repo" not in pr_body
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in pr_body
    assert "pip install" not in pr_body
    assert "secrets." not in pr_body
