# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Regression tests for required CI, live-network, and dependency policy."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PIP_EXECUTORS = [
    ROOT / "Containerfile.dev",
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / ".github" / "workflows" / "dependency-review.yml",
    ROOT / ".github" / "workflows" / "validate.yml",
    ROOT / ".github" / "scripts" / "compatibility.py",
]


def test_no_github_actions_workflow_is_scheduled() -> None:
    """All repository workflows must be event-driven or manually dispatched."""
    scheduled = [
        workflow.name
        for workflow in WORKFLOWS.glob("*.yml")
        if "\n  schedule:" in workflow.read_text(encoding="utf-8")
    ]

    assert scheduled == []


def test_live_fmi_is_required_after_offline_tests_for_pr_and_master() -> None:
    """PRs and every master release run execute bounded live probes before success."""
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")

    assert not (WORKFLOWS / "live-fmi.yml").exists()
    assert "pull_request:" in ci
    assert "workflow_call:" in ci
    assert ci.index("- name: Offline tests and coverage") < ci.index(
        "- name: Run bounded live FMI probes"
    )
    assert "--strict-markers" in ci
    assert "-m live" in ci

    ci_release_job = release.split("\n  ci:\n", maxsplit=1)[1].split("\n  validate:\n", maxsplit=1)[
        0
    ]
    assert "uses: ./.github/workflows/ci.yml" in ci_release_job
    assert "needs:" not in ci_release_job
    assert "push:" in release
    assert "- master" in release


def test_pip_installs_use_requirement_files_without_inline_versions() -> None:
    """Every maintained pip install consumes files instead of package arguments."""
    for path in PIP_EXECUTORS:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if 'pip", "install"' in line or "pip install" in line:
                assert "==" not in line, path

    workflows = "\n".join(
        workflow.read_text(encoding="utf-8") for workflow in WORKFLOWS.glob("*.yml")
    )
    assert "pip==" not in workflows
    assert "homeassistant==" not in workflows
    assert "pytest-homeassistant-custom-component==" not in workflows


def test_local_image_names_remain_stable() -> None:
    """Dependency refreshes must not require local image-name changes."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "LOCAL_IMAGE_PREFIX ?= localhost/fmi-hass-custom" in makefile
    assert "LOCK_IMAGE ?= $(LOCAL_IMAGE_PREFIX)-lock:local" in makefile
    assert "DEV_IMAGE ?= $(LOCAL_IMAGE_PREFIX)-dev:local" in makefile
    assert "DEV_STAMP ?= .cache/podman-dev.stamp" in makefile


def test_compatibility_resolves_current_channels_and_freezes_before_testing() -> None:
    """Event/manual compatibility jobs recreate moving graphs without release pins."""
    workflow = (WORKFLOWS / "compatibility.yml").read_text(encoding="utf-8")
    helper = (ROOT / ".github" / "scripts" / "compatibility.py").read_text(encoding="utf-8")

    assert "latest-stable:" in workflow
    assert "latest-prerelease:" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "workflow_dispatch:" in workflow
    prerelease_job = workflow.split("\n  latest-prerelease:\n", maxsplit=1)[1]
    assert "continue-on-error: true" in prerelease_job
    assert '"--pre"' in helper
    assert '"freeze"' in helper
    assert helper.index("_freeze(resolver_python, output)") < helper.index(
        '_install(runner_python, "--no-deps", "-r", str(output))'
    )

    for path in (
        ROOT / "requirements-compatibility-homeassistant.txt",
        ROOT / "requirements-compatibility-direct.txt",
    ):
        packages = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        assert packages
        assert all("==" not in package for package in packages)


def test_safe_branch_workflows_share_standard_event_matrix() -> None:
    """Read-only branch checks share PR/push/manual events; exceptions stay narrow."""
    for name in (
        "ci.yml",
        "codeql.yml",
        "compatibility.yml",
        "validate.yml",
        "version.yml",
    ):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        for event in ("pull_request:", "push:", "workflow_dispatch:"):
            assert event in workflow, (name, event)
        assert "- master" in workflow, name

    version = (WORKFLOWS / "version.yml").read_text(encoding="utf-8")
    assert "base_ref:" in version
    assert "default: master" in version
    assert "github.event.pull_request.base.sha || github.event.before || inputs.base_ref" in version
    assert "github.event.pull_request.head.sha || github.sha" in version

    for name in ("dependency-review.yml", "pr-body.yml", "release.yml"):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" not in workflow, name

    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/ci.yml" in release
    assert "uses: ./.github/workflows/validate.yml" in release
    assert "- version" in release


def test_dependency_review_uses_supported_fork_fallback() -> None:
    """Forks use the frozen audit; independent repositories retain native review."""
    workflow = (WORKFLOWS / "dependency-review.yml").read_text(encoding="utf-8")

    assert "actions/dependency-review-action@" in workflow
    assert "if: github.event.repository.fork == false" in workflow
    assert workflow.count("if: github.event.repository.fork") == 4
    assert "python .github/scripts/dependency_audit.py" in workflow
    assert "python -m pip install --no-deps -r requirements.txt" in workflow
