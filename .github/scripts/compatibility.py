# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Resolve, freeze, recreate, and test a current Home Assistant environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

HOME_ASSISTANT = "homeassistant"
TEST_HELPER = "pytest-homeassistant-custom-component"


class CompatibilityError(RuntimeError):
    """Raised when a compatibility environment violates its channel contract."""


class CompatibilityUnavailable(CompatibilityError):
    """Raised when an informational compatibility channel has no candidate."""


def _run(
    command: list[str],
    *,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run one environment command with visible arguments and deterministic errors."""
    print("+", " ".join(command), flush=True)
    return subprocess.run(
        command,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _python(environment: Path) -> str:
    """Return the Python executable in a POSIX virtual environment."""
    return str(environment / "bin" / "python")


def _install(python: str, *arguments: str) -> None:
    """Install only from requirement/constraint files."""
    if "-r" not in arguments:
        raise CompatibilityError("pip install must receive a requirements file")
    _run([python, "-m", "pip", "install", *arguments])


def _distribution_version(python: str, distribution: str) -> str:
    """Read one installed distribution version inside the selected environment."""
    code = (
        "import importlib.metadata, sys; sys.stdout.write(importlib.metadata.version(sys.argv[1]))"
    )
    result = _run([python, "-c", code, distribution], capture_output=True)
    return result.stdout.strip()


def _is_prerelease(version: str) -> bool:
    """Classify the calendar-version prerelease suffixes published by Home Assistant."""
    normalized = version.lower()
    return any(marker in normalized for marker in ("a", "b", "rc", "dev"))


def _assert_channel(
    python: str,
    channel: str,
    *,
    allow_unavailable: bool = False,
) -> str:
    """Require the resolver result to match the requested stable/prerelease channel."""
    version = _distribution_version(python, HOME_ASSISTANT)
    prerelease = _is_prerelease(version)
    if channel == "stable" and prerelease:
        raise CompatibilityError(f"stable resolution selected prerelease Home Assistant {version}")
    if channel == "prerelease" and not prerelease:
        if allow_unavailable:
            raise CompatibilityUnavailable(
                "no newer installable Home Assistant prerelease is available; "
                f"the resolver selected stable {version}"
            )
        raise CompatibilityError(f"no current Home Assistant prerelease was selected: {version}")
    return version


def _freeze(python: str, output: Path) -> None:
    """Write the complete transitive graph selected by pip."""
    result = _run([python, "-m", "pip", "freeze"], capture_output=True)
    if not result.stdout.strip():
        raise CompatibilityError("pip freeze produced an empty environment")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout, encoding="utf-8")


def _moving_inputs(project: Path, root: Path) -> tuple[Path, Path]:
    """Derive unpinned moving inputs from the reviewed PEP 621 direct set."""
    try:
        metadata = tomllib.loads(project.read_text(encoding="utf-8"))["project"]
        runtime = metadata["dependencies"]
        development = metadata["optional-dependencies"]["dev"]
    except (KeyError, OSError, tomllib.TOMLDecodeError, TypeError) as error:
        raise CompatibilityError(f"cannot read project dependency metadata: {error}") from error
    if not isinstance(runtime, list) or not isinstance(development, list):
        raise CompatibilityError("project dependencies and dev extra must be lists")

    try:
        runtime_requirements = [Requirement(item) for item in runtime]
        development_requirements = [Requirement(item) for item in development]
    except (TypeError, ValueError) as error:
        raise CompatibilityError(f"invalid project requirement: {error}") from error

    development_by_name = {
        canonicalize_name(requirement.name): requirement for requirement in development_requirements
    }
    for required in (HOME_ASSISTANT, TEST_HELPER):
        if canonicalize_name(required) not in development_by_name:
            raise CompatibilityError(f"dev dependencies omit required moving input: {required}")

    root.mkdir(parents=True, exist_ok=True)
    homeassistant = root / "requirements-homeassistant.txt"
    project_inputs = root / "requirements-project.txt"
    homeassistant.write_text(f"{HOME_ASSISTANT}\n", encoding="utf-8")
    direct_names = [requirement.name for requirement in runtime_requirements]
    direct_names.append(TEST_HELPER)
    project_inputs.write_text("".join(f"{name}\n" for name in direct_names), encoding="utf-8")
    return homeassistant, project_inputs


def _check_dependencies(python: str, channel: str) -> None:
    """Reject dependency errors except a known moving beta/helper HA constraint."""
    result = _run(
        [python, "-m", "pip", "check"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        print(result.stdout, end="")
        return

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    allowed_prefix = f"{TEST_HELPER} "
    unexpected = [
        line
        for line in lines
        if channel != "prerelease"
        or not line.startswith(allowed_prefix)
        or " has requirement homeassistant" not in line
    ]
    if unexpected or not lines:
        raise CompatibilityError(
            "dependency metadata is inconsistent: " + "; ".join(unexpected or lines)
        )
    print("Informational prerelease harness mismatch:")
    print("\n".join(lines))


def _resolve(
    *,
    channel: str,
    project: Path,
    output: Path,
) -> None:
    """Resolve current packages, freeze them, recreate them, and run the suite."""
    if not project.is_file():
        raise CompatibilityError(f"project metadata is missing: {project}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"fmi-{channel}-") as temporary:
        root = Path(temporary)
        homeassistant, direct = _moving_inputs(project, root)
        resolver = root / "resolver"
        runner = root / "runner"
        venv.EnvBuilder(with_pip=True).create(resolver)
        resolver_python = _python(resolver)

        if channel == "stable":
            _install(resolver_python, "--upgrade", "-r", str(homeassistant))
            selected = _distribution_version(resolver_python, HOME_ASSISTANT)
            constraint = root / "requirements-homeassistant-selected.txt"
            constraint.write_text(f"{HOME_ASSISTANT}=={selected}\n", encoding="utf-8")
            _install(
                resolver_python,
                "--upgrade",
                "-c",
                str(constraint),
                "-r",
                str(direct),
            )
        else:
            _install(resolver_python, "--upgrade", "-r", str(direct))
            _install(resolver_python, "--upgrade", "--pre", "-r", str(homeassistant))

        resolved_version = _assert_channel(
            resolver_python,
            channel,
            allow_unavailable=channel == "prerelease",
        )
        _freeze(resolver_python, output)

        venv.EnvBuilder(with_pip=True).create(runner)
        runner_python = _python(runner)
        _install(runner_python, "--no-deps", "-r", str(output))
        recreated_version = _assert_channel(runner_python, channel)
        if recreated_version != resolved_version:
            raise CompatibilityError(
                f"recreated Home Assistant {recreated_version} does not match {resolved_version}"
            )
        _check_dependencies(runner_python, channel)
        helper_version = _distribution_version(runner_python, TEST_HELPER)
        print(
            f"Testing Home Assistant {recreated_version} with {TEST_HELPER} {helper_version}",
            flush=True,
        )
        _run(
            [
                runner_python,
                "-m",
                "pytest",
                "-n",
                "auto",
                "--dist=worksteal",
                "-q",
            ]
        )


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", choices=("stable", "prerelease"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run the selected compatibility environment."""
    args = _parser().parse_args()
    try:
        _resolve(
            channel=args.channel,
            project=args.project.resolve(),
            output=args.output.resolve(),
        )
    except CompatibilityUnavailable as error:
        print(f"Informational compatibility check skipped: {error}")
        return 0
    except (CompatibilityError, OSError, subprocess.CalledProcessError) as error:
        print(f"compatibility error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
