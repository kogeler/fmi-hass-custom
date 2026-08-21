# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Validate normative contract structure, traceability, and code ownership."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from custom_components.fmi import const
from custom_components.fmi import sensor as sensor_platform
from custom_components.fmi import weather as weather_platform

ROOT = Path(__file__).parents[1]
CONTRACTS = ROOT / "docs" / "contracts"
CURRENT_DOCUMENTATION = (
    *ROOT.glob("*.md"),
    *(ROOT / "docs").rglob("*.md"),
    ROOT / "plans" / "README.md",
    ROOT / "tests" / "fixtures" / "fmi" / "README.md",
)

EXPECTED_CONTRACTS = {
    "AVAILABILITY.md": "AVL",
    "CI.md": "CIR",
    "COMPATIBILITY_SECURITY.md": "CSP",
    "DEPENDENCIES.md": "DEP",
    "FORECAST_SEMANTICS.md": "FCS",
    "LIVE_TESTS.md": "LIV",
    "MIGRATIONS.md": "MIG",
    "OPTIONAL_SOURCES.md": "OPT",
    "RECONFIGURATION.md": "RCF",
    "RUNTIME.md": "RUN",
    "SENSORS.md": "SNS",
    "TIME_AND_MISSING_DATA.md": "TIM",
}

IMPLEMENTATION_OWNERS = {
    "custom_components/fmi/__init__.py": {
        "docs/contracts/AVAILABILITY.md",
        "docs/contracts/OPTIONAL_SOURCES.md",
        "docs/contracts/RUNTIME.md",
    },
    "custom_components/fmi/best_time.py": {"docs/contracts/TIME_AND_MISSING_DATA.md"},
    "custom_components/fmi/config_flow.py": {
        "docs/contracts/COMPATIBILITY_SECURITY.md",
        "docs/contracts/MIGRATIONS.md",
        "docs/contracts/RECONFIGURATION.md",
    },
    "custom_components/fmi/const.py": {
        "docs/contracts/MIGRATIONS.md",
        "docs/contracts/OPTIONAL_SOURCES.md",
        "docs/contracts/RUNTIME.md",
        "docs/contracts/SENSORS.md",
        "docs/contracts/TIME_AND_MISSING_DATA.md",
    },
    "custom_components/fmi/diagnostics.py": {"docs/contracts/COMPATIBILITY_SECURITY.md"},
    "custom_components/fmi/fmi_client.py": {
        "docs/contracts/COMPATIBILITY_SECURITY.md",
        "docs/contracts/RUNTIME.md",
        "docs/contracts/SENSORS.md",
    },
    "custom_components/fmi/lightning.py": {"docs/contracts/OPTIONAL_SOURCES.md"},
    "custom_components/fmi/sensor.py": {
        "docs/contracts/MIGRATIONS.md",
        "docs/contracts/SENSORS.md",
        "docs/contracts/TIME_AND_MISSING_DATA.md",
    },
    "custom_components/fmi/utils.py": {
        "docs/contracts/OPTIONAL_SOURCES.md",
        "docs/contracts/TIME_AND_MISSING_DATA.md",
    },
    "custom_components/fmi/weather.py": {
        "docs/contracts/FORECAST_SEMANTICS.md",
        "docs/contracts/TIME_AND_MISSING_DATA.md",
    },
    "custom_components/fmi/xml_parser.py": {"docs/contracts/COMPATIBILITY_SECURITY.md"},
}

MAINTENANCE_OWNERS = {
    "AVAILABILITY.md": "AVAILABILITY.md",
    "CI.md": "CI.md",
    "COMPATIBILITY_SECURITY.md": "COMPATIBILITY_SECURITY.md",
    "DEPENDENCIES.md": "DEPENDENCIES.md",
    "DEVELOPMENT.md": "DEPENDENCIES.md",
    "FORECAST_SEMANTICS.md": "FORECAST_SEMANTICS.md",
    "HACS_RELEASES.md": "CI.md",
    "HA_RELEASE_MAINTENANCE.md": "CI.md",
    "LIVE_TESTS.md": "LIVE_TESTS.md",
    "MIGRATIONS.md": "MIGRATIONS.md",
    "OPTIONAL_SOURCES.md": "OPTIONAL_SOURCES.md",
    "RECONFIGURATION.md": "RECONFIGURATION.md",
    "RUNTIME.md": "RUNTIME.md",
    "SENSORS.md": "SENSORS.md",
    "TIME_AND_MISSING_DATA.md": "TIME_AND_MISSING_DATA.md",
}

ASSERTION_HEADING = re.compile(r"^### `(?P<id>[A-Z]{3}-[0-9]{3})` — .+$", re.MULTILINE)
EVIDENCE_LINK = re.compile(
    r"^- \[`(?P<test>test_[a-z0-9_]+)`\]"
    r"\(\.\./\.\./(?P<path>tests/[a-z0-9_/]+\.py)\)"
    r" — `(?P=path)::(?P=test)`$",
    re.MULTILINE,
)
NORMATIVE_KEYWORD = re.compile(r"\b(?:MUST|MUST NOT|SHOULD|SHOULD NOT|MAY)\b")
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\((?P<target><[^>]+>|[^)\s]+)\)")
MAKE_REFERENCE = re.compile(r"`make (?P<target>[a-z0-9][a-z0-9_-]*)")
MAKE_TARGET = re.compile(r"^(?P<target>[a-z0-9][a-z0-9_-]*):(?:\s|$)", re.MULTILINE)


def _without_fenced_code(content: str) -> str:
    """Exclude illustrative Markdown code blocks from repository-link validation."""
    return re.sub(r"^```.*?^```[ \t]*$", "", content, flags=re.MULTILINE | re.DOTALL)


def test_contract_catalog_is_complete_and_has_unique_traceable_assertions() -> None:
    """Require every normative statement to have a stable ID and real pytest evidence."""
    files = {path.name for path in CONTRACTS.glob("*.md") if path.name != "README.md"}
    assert files == set(EXPECTED_CONTRACTS)

    index = (CONTRACTS / "README.md").read_text(encoding="utf-8")
    seen_ids: set[str] = set()
    for filename, prefix in EXPECTED_CONTRACTS.items():
        assert f"]({filename})" in index
        content = (CONTRACTS / filename).read_text(encoding="utf-8")
        headings = list(ASSERTION_HEADING.finditer(content))
        assert headings, filename
        assert content.count("\n### ") == len(headings), filename

        for position, heading in enumerate(headings):
            assertion_id = heading.group("id")
            assert assertion_id.startswith(f"{prefix}-"), assertion_id
            assert assertion_id not in seen_ids, assertion_id
            seen_ids.add(assertion_id)

            end = headings[position + 1].start() if position + 1 < len(headings) else len(content)
            block = content[heading.end() : end]
            assert block.count("**Contract:**") == 1, assertion_id
            assert block.count("**Evidence:**") == 1, assertion_id
            contract_text, evidence_text = block.split("**Evidence:**", maxsplit=1)
            assert NORMATIVE_KEYWORD.search(contract_text), assertion_id

            links = list(EVIDENCE_LINK.finditer(evidence_text))
            assert links, assertion_id
            assert len(links) == evidence_text.count("\n- ["), assertion_id
            for link in links:
                test_path = ROOT / link.group("path")
                assert test_path.is_file(), (assertion_id, test_path)
                definition = re.compile(
                    rf"^(?:async )?def {re.escape(link.group('test'))}\(", re.MULTILINE
                )
                assert definition.search(test_path.read_text(encoding="utf-8")), (
                    assertion_id,
                    link.group("test"),
                )


def test_contract_relative_markdown_links_resolve() -> None:
    """Keep internal contract cross-references navigable on GitHub and in a clone."""
    link_pattern = re.compile(r"\[[^]]+\]\((?P<target>[^)]+\.md)\)")
    for path in CONTRACTS.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            target = (path.parent / match.group("target")).resolve()
            assert target.is_file(), (path, match.group("target"))


def test_current_documentation_links_and_make_targets_resolve() -> None:
    """Keep current documentation navigable and limited to the supported command surface."""
    makefiles = (ROOT / "Makefile", *(ROOT / "make").glob("*.mk"))
    make_targets = {
        match.group("target")
        for path in makefiles
        for match in MAKE_TARGET.finditer(path.read_text(encoding="utf-8"))
    }

    for path in CURRENT_DOCUMENTATION:
        content = _without_fenced_code(path.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK.finditer(content):
            raw_target = match.group("target").strip("<>")
            if raw_target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_target = raw_target.split("#", maxsplit=1)[0]
            assert (path.parent / relative_target).resolve().exists(), (path, raw_target)

        for match in MAKE_REFERENCE.finditer(content):
            assert match.group("target") in make_targets, (path, match.group("target"))


def test_completed_plans_are_explicitly_archived() -> None:
    """Prevent dated execution records from masquerading as current documentation."""
    archive_index = (ROOT / "plans" / "README.md").read_text(encoding="utf-8")
    for plan in sorted((ROOT / "plans").glob("P*/PLAN.md")):
        plan_name = plan.parent.name
        content = plan.read_text(encoding="utf-8")
        assert "**Archive notice:**" in content[:1500], plan
        assert "../../docs/contracts/README.md" in content[:1500], plan
        assert f"]({plan_name}/PLAN.md)" in archive_index, plan_name


def test_implementation_and_maintenance_docs_link_to_contract_owners() -> None:
    """Make contracts the discoverable owner instead of a disconnected duplicate."""
    for relative_path, contracts in IMPLEMENTATION_OWNERS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "# Contracts:" in content, relative_path
        for contract in contracts:
            assert contract in content, (relative_path, contract)

    maintenance = ROOT / "docs" / "maintenance"
    for filename, contract in MAINTENANCE_OWNERS.items():
        content = (maintenance / filename).read_text(encoding="utf-8")
        assert f"../contracts/{contract}" in content, filename
        assert "**Contract:**" not in content, filename
        assert ASSERTION_HEADING.search(content) is None, filename


def test_runtime_cadence_and_platform_parallelism_match_contract() -> None:
    """Pin previously documented but untested coordinator/platform timing invariants."""
    assert const.FORECAST_UPDATE_INTERVAL == timedelta(minutes=30)
    assert const.OBSERVATION_UPDATE_INTERVAL == timedelta(minutes=10)
    assert sensor_platform.PARALLEL_UPDATES == 0
    assert weather_platform.PARALLEL_UPDATES == 0
