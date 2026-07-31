"""Validate the repository installation layout."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "fmi"


def test_standard_custom_component_layout() -> None:
    """Ensure HACS/manual installation uses the standard directory."""
    required_files = {
        "__init__.py",
        "config_flow.py",
        "const.py",
        "manifest.json",
        "sensor.py",
        "strings.json",
        "utils.py",
        "weather.py",
    }

    assert required_files <= {path.name for path in INTEGRATION.iterdir()}

    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == INTEGRATION.name
    assert "content_in_root" not in hacs
