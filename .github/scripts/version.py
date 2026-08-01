# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Validate and synchronize release metadata from the root .version file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = "kogeler/fmi-hass-custom"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


class VersionError(ValueError):
    """Raised when release metadata violates the repository contract."""


@dataclass(frozen=True, order=True)
class Version:
    """Strict stable semantic version."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str, *, source: str) -> Version:
        """Parse a stable X.Y.Z version without prefixes or prerelease suffixes."""
        normalized = value.strip()
        match = VERSION_PATTERN.fullmatch(normalized)
        if match is None:
            raise VersionError(f"{source} must contain exactly one stable X.Y.Z version")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        """Return the canonical stable semantic version."""
        return f"{self.major}.{self.minor}.{self.patch}"


def _read_version(root: Path) -> Version:
    """Read the only human-maintained version source."""
    path = root / ".version"
    if not path.is_file():
        raise VersionError(".version is missing")
    return Version.parse(path.read_text(encoding="utf-8"), source=".version")


def _read_manifest(root: Path) -> dict[str, object]:
    """Read and validate the integration manifest object."""
    path = root / "custom_components" / "fmi" / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise VersionError(f"cannot read manifest.json: {err}") from err
    if not isinstance(manifest, dict):
        raise VersionError("manifest.json must contain a JSON object")
    return manifest


def _manifest_version(root: Path) -> Version:
    """Read the generated version mirror from manifest.json."""
    value = _read_manifest(root).get("version")
    if not isinstance(value, str):
        raise VersionError("manifest.json version must be a string")
    return Version.parse(value, source="manifest.json version")


def _changelog_body(root: Path, version: Version) -> str:
    """Extract exactly one non-empty changelog section for a version."""
    path = root / "CHANGELOG.md"
    try:
        changelog = path.read_text(encoding="utf-8")
    except OSError as err:
        raise VersionError(f"cannot read CHANGELOG.md: {err}") from err

    heading = re.compile(
        rf"^## {re.escape(str(version))} - [0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$",
        re.MULTILINE,
    )
    matches = list(heading.finditer(changelog))
    if len(matches) != 1:
        raise VersionError(
            f"CHANGELOG.md must contain exactly one '## {version} - YYYY-MM-DD' section"
        )

    start = matches[0].end()
    next_heading = re.search(r"^## ", changelog[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading is not None else len(changelog)
    body = changelog[start:end].strip()
    if not body or not re.search(r"^- ", body, re.MULTILINE):
        raise VersionError(f"CHANGELOG.md section {version} must contain release entries")
    return body


def _validate_current(root: Path) -> Version:
    """Validate every committed version mirror and release-note source."""
    version = _read_version(root)
    manifest_version = _manifest_version(root)
    if manifest_version != version:
        raise VersionError(
            f"manifest.json version {manifest_version} does not match .version {version}; "
            "run the version sync command"
        )
    _changelog_body(root, version)
    return version


def _version_from_base_tree(root: Path) -> Version:
    """Read a checked-out base tree, falling back to its legacy manifest version."""
    version_path = root / ".version"
    if version_path.is_file():
        return Version.parse(version_path.read_text(encoding="utf-8"), source="base .version")
    try:
        value = _read_manifest(root)["version"]
    except KeyError as err:
        raise VersionError("base manifest.json has no version") from err
    if not isinstance(value, str):
        raise VersionError("base manifest.json version must be a string")
    return Version.parse(value, source="base manifest.json version")


def _require_increment(current: Version, base: Version) -> None:
    """Require a strict semantic version increase."""
    if current <= base:
        raise VersionError(f".version {current} must be greater than base version {base}")


def _sync_manifest(root: Path, *, check: bool) -> Version:
    """Synchronize the generated manifest version mirror."""
    version = _read_version(root)
    path = root / "custom_components" / "fmi" / "manifest.json"
    manifest = _read_manifest(root)
    existing = manifest.get("version")
    if existing == str(version):
        return version
    if check:
        raise VersionError(
            f"manifest.json version {existing!r} does not match .version {version}; "
            "run the version sync command"
        )
    manifest["version"] = str(version)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return version


def _release_notes(root: Path, version: Version) -> str:
    """Build a release body from the matching changelog section."""
    body = _changelog_body(root, version)
    changelog_url = f"{REPOSITORY_URL}/blob/{version}/CHANGELOG.md"
    return f"{body}\n\nFull changelog: {changelog_url}\n"


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate current metadata and version progression")
    base = check.add_mutually_exclusive_group()
    base.add_argument("--base-root", type=Path)
    base.add_argument("--base-version")

    sync = commands.add_parser("sync", help="copy .version into generated metadata")
    sync.add_argument("--check", action="store_true")

    notes = commands.add_parser("notes", help="write release notes for the current version")
    notes.add_argument("--output", type=Path, required=True)

    commands.add_parser("current", help="print the current version")
    return parser


def _run(args: argparse.Namespace) -> None:
    """Execute a parsed command."""
    root = args.root.resolve()
    if args.command == "sync":
        print(_sync_manifest(root, check=args.check))
        return
    if args.command == "current":
        print(_read_version(root))
        return

    version = _validate_current(root)
    if args.command == "check":
        if args.base_root is not None:
            _require_increment(version, _version_from_base_tree(args.base_root.resolve()))
        elif args.base_version is not None:
            base = Version.parse(args.base_version, source="--base-version")
            _require_increment(version, base)
        print(version)
        return
    if args.command == "notes":
        args.output.write_text(_release_notes(root, version), encoding="utf-8")
        print(version)
        return
    raise AssertionError(f"unhandled command {args.command}")


def main() -> int:
    """Run the CLI and return a process exit status."""
    try:
        _run(_build_parser().parse_args())
    except VersionError as err:
        print(f"version error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
