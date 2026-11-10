# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Failure-oriented tests for warning coverage across pre-existing platform files."""

import runpy
from pathlib import Path
from typing import Any


def test_warning_coverage_rejects_missing_lines_branches_and_renamed_scopes(tmp_path):
    helper = runpy.run_path(str(Path(__file__).parents[1] / ".github/scripts/warning_coverage.py"))
    scopes, check = helper["SCOPES"], helper["check_warning_coverage"]
    files: dict[str, Any] = {}
    for filename, names in scopes.items():
        relative = "custom_components/fmi/" + filename
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"def {name}():\n    return 1\n" for name in sorted(names)))
        files[relative] = {"missing_lines": [], "missing_branches": []}
    report = {"files": files}
    assert check(tmp_path, report) == []
    first = files["custom_components/fmi/__init__.py"]
    first["missing_lines"] = [2]
    assert "missing lines [2]" in str(check(tmp_path, report))
    first["missing_lines"] = []
    first["missing_branches"] = [[1, 2]]
    assert "branches [[1, 2]]" in str(check(tmp_path, report))
    first["missing_branches"] = [[10000, 10001]]
    assert check(tmp_path, report) == []
    (tmp_path / "custom_components/fmi/__init__.py").write_text("pass\n")
    assert "missing coverage scopes" in str(check(tmp_path, report))
