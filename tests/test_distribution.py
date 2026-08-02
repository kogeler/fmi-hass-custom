# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Prove the integration works from the tree delivered by HACS/manual install."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "fmi"
CURRENT_FACING_DOCS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "USER_GUIDE.md",
)


def test_hacs_release_metadata_and_brand() -> None:
    """Keep the HACS repository metadata aligned with the supported release."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert hacs == {
        "name": "FMI",
        "country": "FI",
        "homeassistant": "2026.7.4",
        "render_readme": True,
    }

    icon_path = INTEGRATION / "brand" / "icon.png"
    with Image.open(icon_path) as icon:
        assert icon.format == "PNG"
        assert icon.width == icon.height
        assert icon.width >= 128


def test_current_facing_docs_use_the_latest_release_instead_of_version_literals() -> None:
    """Keep mutable project and HA versions out of current-facing documentation."""
    for path in CURRENT_FACING_DOCS:
        content = path.read_text(encoding="utf-8")
        assert re.search(r"\b[0-9]+\.[0-9]+\.[0-9]+\b", content) is None, path

    for path in (ROOT / "README.md", ROOT / "docs" / "USER_GUIDE.md"):
        assert "https://github.com/kogeler/fmi-hass-custom/releases/latest" in path.read_text(
            encoding="utf-8"
        )


def test_copied_distribution_imports_from_empty_config(tmp_path: Path) -> None:
    """Import a clean copy from the path HACS/manual installation creates."""
    installed = tmp_path / "config" / "custom_components" / "fmi"
    shutil.copytree(
        INTEGRATION,
        installed,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    assert not list(installed.rglob("__pycache__"))
    assert not list(installed.rglob("*.pyc"))
    assert (installed / "manifest.json").is_file()
    assert (installed / "translations" / "en.json").is_file()

    package_name = "fmi_distribution_smoke"
    spec = importlib.util.spec_from_file_location(
        package_name,
        installed / "__init__.py",
        submodule_search_locations=[str(installed)],
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    try:
        spec.loader.exec_module(module)
        assert module.PLATFORMS
    finally:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                del sys.modules[name]
