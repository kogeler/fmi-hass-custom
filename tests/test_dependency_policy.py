# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Repository policy for dependency environments and confined execution."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import homeassistant
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).parents[1]
LOCK_PIN = re.compile(r"^([A-Za-z0-9._-]+)==([^\s\\]+)")
MAKE_TARGET = re.compile(r"^([a-z][a-z0-9-]*):", re.MULTILINE)


def _read_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LOCK_PIN.match(line)
        if match:
            name = canonicalize_name(match.group(1))
            assert name not in pins, f"duplicate lock pin: {path.name}: {name}"
            pins[name] = match.group(2)
    return pins


def _exact(requirement: str) -> tuple[str, str]:
    parsed = Requirement(requirement)
    specifiers = list(parsed.specifier)
    assert parsed.url is None
    assert parsed.marker is None
    assert len(specifiers) == 1 and specifiers[0].operator == "==", requirement
    return canonicalize_name(parsed.name), specifiers[0].version


def _project(path: Path) -> dict[str, Any]:
    project: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    return project


def test_pep621_owns_every_direct_python_dependency() -> None:
    """Runtime, development, and host Ruff inputs have one explicit owner each."""
    project = _project(ROOT / "pyproject.toml")
    lint_project = _project(ROOT / "tools/lint/pyproject.toml")
    manifest = json.loads(
        (ROOT / "custom_components/fmi/manifest.json").read_text(encoding="utf-8")
    )

    runtime = dict(_exact(item) for item in project["dependencies"])
    manifest_names = {
        canonicalize_name(Requirement(item).name) for item in manifest["requirements"]
    }
    assert manifest_names == set(runtime)
    assert set(runtime) == {"fmi-weather-client", "xmltodict"}

    development = dict(_exact(item) for item in project["optional-dependencies"]["dev"])
    assert set(project["optional-dependencies"]) == {"dev"}
    assert set(development) == {
        "bandit",
        "homeassistant",
        "mypy",
        "packaging",
        "pip-audit",
        "pip-licenses",
        "pylint",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-homeassistant-custom-component",
        "pytest-socket",
        "pytest-xdist",
    }
    lint = dict(_exact(item) for item in lint_project["dependencies"])
    assert set(lint) == {"ruff"}


def _core_integration_pins() -> dict[str, set[str]]:
    """Return exact versions that integrations bundled with reference Home Assistant require."""
    pins: dict[str, set[str]] = {}
    for path in (Path(homeassistant.__file__).parent / "components").glob("*/manifest.json"):
        for item in json.loads(path.read_text(encoding="utf-8")).get("requirements", []):
            try:
                requirement = Requirement(item)
            except InvalidRequirement:
                continue
            versions = {spec.version for spec in requirement.specifier if spec.operator == "=="}
            pins.setdefault(canonicalize_name(requirement.name), set()).update(versions)
    return pins


def test_manifest_requirements_follow_home_assistant_core_pins() -> None:
    """Share core packages as minimums and test them at the reference Home Assistant version."""
    runtime = dict(_exact(item) for item in _project(ROOT / "pyproject.toml")["dependencies"])
    manifest = json.loads(
        (ROOT / "custom_components/fmi/manifest.json").read_text(encoding="utf-8")
    )
    core = _core_integration_pins()

    for item in manifest["requirements"]:
        declared = Requirement(item)
        name = canonicalize_name(declared.name)
        specifiers = list(declared.specifier)
        assert declared.url is None and declared.marker is None and not declared.extras, item
        assert len(specifiers) == 1, item
        if name in core:
            assert core[name] == {runtime[name]}, f"{name}: pin the reference core version"
            assert specifiers[0].operator == ">=", item
            assert declared.specifier.contains(runtime[name]), item
        else:
            assert specifiers[0].operator == "==", item
            assert specifiers[0].version == runtime[name], item


def test_exactly_three_generated_hash_locks_are_split_by_audience() -> None:
    """The runtime, toolbox, and Ruff environments cannot silently merge."""
    lock_paths = sorted(ROOT.glob("requirements*.txt"))
    assert [path.name for path in lock_paths] == [
        "requirements-dev.txt",
        "requirements-lint.txt",
        "requirements.txt",
    ]
    assert not (ROOT / "requirements").exists()
    assert not list(ROOT.rglob("*.in"))

    runtime = _read_lock(ROOT / "requirements.txt")
    development = _read_lock(ROOT / "requirements-dev.txt")
    lint = _read_lock(ROOT / "requirements-lint.txt")
    assert set(runtime) <= set(development)
    assert all(development[name] == version for name, version in runtime.items())
    assert "ruff" not in development
    assert "pip-tools" not in development
    lint_project = _project(ROOT / "tools/lint/pyproject.toml")
    assert lint == dict(_exact(item) for item in lint_project["dependencies"])

    for path in lock_paths:
        content = path.read_text(encoding="utf-8")
        assert "autogenerated by pip-compile" in content
        assert "--hash=sha256:" in content
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "chmod 0644 $(RUNTIME_LOCK) $(DEVELOPMENT_LOCK) $(LINT_LOCK)" in makefile


def test_resolver_bootstrap_is_the_only_inline_install_set() -> None:
    """The self-hosting resolver exception remains exact, complete, and wheel-only."""
    containerfile = (ROOT / "containers/toolbox/Containerfile").read_text(encoding="utf-8")
    lock_stage = containerfile.split("FROM base AS lock", maxsplit=1)[1].split(
        "FROM base AS dev", maxsplit=1
    )[0]
    assert "--only-binary=:all:" in lock_stage
    assert "--require-hashes" not in lock_stage
    _, install = lock_stage.split("pip install", maxsplit=1)
    assert "pip install" not in install
    arguments = install.split("\n\n", maxsplit=1)[0].replace("\\\n", " ").split()
    bootstrap = dict(_exact(item) for item in arguments if not item.startswith("-"))
    assert set(bootstrap) == {
        "build",
        "click",
        "packaging",
        "pip",
        "pip-tools",
        "pyproject-hooks",
        "setuptools",
        "wheel",
    }

    dev_stage = containerfile.split("FROM base AS dev", maxsplit=1)[1]
    assert "--require-hashes" in dev_stage
    assert "requirements-dev.txt" in dev_stage
    assert "python -m pip check" in dev_stage
    assert "==" not in dev_stage
    assert "COPY ." not in containerfile

    for path in [ROOT / "Makefile", *sorted((ROOT / ".github").rglob("*.py"))]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "pip install" in line or '"pip", "install"' in line:
                assert "==" not in line, path


def test_toolbox_policy_streams_source_and_enforces_confinement() -> None:
    """Project-aware containers never receive the host checkout as a mount."""
    policy = (ROOT / "make/container.mk").read_text(encoding="utf-8")
    entrypoint = (ROOT / "containers/toolbox/entrypoint.sh").read_text(encoding="utf-8")
    for flag in (
        "--network=none",
        "--userns=auto:size=2048",
        "--security-opt=no-new-privileges",
        "--cap-drop=ALL",
        "--read-only",
        "--unsetenv-all",
        "--pids-limit=1024",
    ):
        assert flag in policy
    assert "--volume" not in policy
    assert "--mount=type=bind" not in policy
    assert "git ls-files --cached --others --exclude-standard" in policy
    assert '[[ -e "$$path" || -L "$$path" ]]' in policy
    for proof in ("id -u", "CapEff", "NoNewPrivs", "Seccomp"):
        assert proof in entrypoint
    assert "BOX_EXPORT_ON_SUCCESS" in entrypoint


def test_every_pytest_entry_point_uses_automatic_xdist_workers() -> None:
    """No maintained offline, live, network, or compatibility suite is serial."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    compatibility = (ROOT / ".github/scripts/compatibility.py").read_text(encoding="utf-8")
    repository_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "Makefile",
            ROOT / ".github/scripts/compatibility.py",
            *ROOT.glob(".github/workflows/*.yml"),
        ]
    )
    assert "PYTEST_WORKERS ?= auto" in makefile
    assert "-n $(PYTEST_WORKERS) --dist=worksteal" in makefile
    assert '"-n",\n                "auto",' in compatibility
    assert '"--dist=worksteal"' in compatibility
    assert "-n 0" not in repository_text
    assert "PYTEST_WORKERS ?= 0" not in repository_text


def test_make_target_surface_has_no_legacy_or_duplicate_execution_path() -> None:
    """Keep one explicit target graph and serialize its shared state boundaries."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    container = (ROOT / "make/container.mk").read_text(encoding="utf-8")
    targets = set(MAKE_TARGET.findall(makefile + container))
    assert targets == {
        "audit",
        "audit-raw",
        "bandit",
        "check",
        "ci",
        "clean",
        "clean-containers",
        "compatibility-prerelease",
        "compatibility-stable",
        "confinement-test",
        "coverage-report",
        "dependency-snapshot",
        "dev-build",
        "doctor",
        "format",
        "format-check",
        "freeze-check",
        "help",
        "image-key",
        "image-load",
        "image-load-resolver",
        "image-load-toolbox",
        "image-save",
        "image-save-resolver",
        "image-save-toolbox",
        "images",
        "licenses",
        "lint",
        "lint-venv",
        "live",
        "lock",
        "lock-image",
        "outdated",
        "reference-contracts",
        "refresh-dependencies",
        "release-notes",
        "shellcheck",
        "syntax",
        "test-fast",
        "test-full",
        "test-network-block",
        "toolbox-image",
        "type-check",
        "validate",
        "validate-actions",
        "validate-hacs",
        "validate-hassfest",
        "validate-local",
        "validator-image-actionlint",
        "validator-image-hacs",
        "validator-image-hassfest",
        "validator-images",
        "version-check",
        "version-sync",
    }
    assert ".NOTPARALLEL:" in makefile
    assert "freeze-check validate \\\n\tdependency-snapshot" in makefile
    assert "check: lint type-check bandit syntax shellcheck test-full" in makefile
    assert "check: format-check" not in makefile
    assert "development-seed" not in makefile


def test_make_failure_exports_and_coverage_reports_are_unambiguous() -> None:
    """Failed atomic commands emit valid empty tar and partial coverage is not publishable."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    container = (ROOT / "make/container.mk").read_text(encoding="utf-8")
    entrypoint = (ROOT / "containers/toolbox/entrypoint.sh").read_text(encoding="utf-8")
    assert "BOX_EXPORT_ON_SUCCESS" in entrypoint
    assert entrypoint.count("tar --create --file=- --files-from=/dev/null") == 2
    assert "-s $(ARTIFACTS)/coverage.xml" in makefile
    assert "-s $(ARTIFACTS)/$(COVERAGE_REPORT)" in makefile
    assert "-s $(ARTIFACTS)/$(COVERAGE_TOTAL)" in makefile
    assert "rm -rf" not in makefile
    assert "rm -rf" not in container


def test_image_archives_are_content_addressed_atomic_and_verified() -> None:
    """Do not reuse, publish, or accept a partial or incorrectly tagged OCI cache."""
    container = (ROOT / "make/container.mk").read_text(encoding="utf-8")
    assert (
        "TOOLBOX_KEY = $(shell cat $(TOOLBOX_CONTEXT) requirements-dev.txt | sha256sum" in container
    )
    assert "LOCK_KEY = $(shell cat $(LOCK_CONTEXT) | sha256sum" in container
    assert "toolbox=%s\\nresolver=%s\\n" in container
    assert "temporary='$(1).tmp.'$$$$" in container
    assert "mv -f \"$$temporary\" '$(1)'" in container
    assert "cached archive did not restore expected image" in container
    assert "$(PODMAN) image exists '$(2)'" in container
