# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Enforce full coverage of warning integration paths in existing platform modules."""

from __future__ import annotations

import ast
import json
from pathlib import Path

SCOPES = {
    "__init__.py": {"async_setup_entry", "async_unload_entry", "_async_first_refresh"},
    "sensor.py": {"async_setup_entry", "FMIWeatherWarningSensor"},
    "config_flow.py": {"FMIOptionsFlowHandler"},
    "diagnostics.py": {"_coordinator_diagnostics", "async_get_config_entry_diagnostics"},
}


def check_warning_coverage(root: Path, report: dict) -> list[str]:
    """Reject uncovered lines/branches inside whole owning functions, including legacy paths."""
    errors = []
    for filename, names in SCOPES.items():
        path = f"custom_components/fmi/{filename}"
        tree = ast.parse((root / path).read_text(encoding="utf-8"))
        nodes = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        absent = names - nodes.keys()
        if absent:
            errors.append(f"{path}: missing coverage scopes {sorted(absent)}")
            continue
        lines = {
            line
            for name in names
            for line in range(
                nodes[name].lineno, (nodes[name].end_lineno or nodes[name].lineno) + 1
            )
        }
        coverage = report["files"][path]
        missing_lines = sorted(lines.intersection(coverage["missing_lines"]))
        missing_branches = [branch for branch in coverage["missing_branches"] if branch[0] in lines]
        if missing_lines or missing_branches:
            errors.append(f"{path}: missing lines {missing_lines}, branches {missing_branches}")
    return errors


def main() -> None:
    """Consume the same full-run coverage data as the new-module gate."""
    errors = check_warning_coverage(Path.cwd(), json.loads(Path("coverage.json").read_text()))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Warning setup/options/sensor/diagnostics scopes: 100% statements and branches")


if __name__ == "__main__":
    main()
