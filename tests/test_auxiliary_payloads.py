# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Characterize synthetic lightning and sea-level payload handling."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import Any, cast

import pytest

from custom_components import fmi as integration
from custom_components.fmi import FMIDataUpdateCoordinator
from tests.helpers.fmi import load_text_fixture


def _coordinator() -> FMIDataUpdateCoordinator:
    coordinator = object.__new__(FMIDataUpdateCoordinator)
    coordinator.latitude = 60.17
    coordinator.longitude = 24.94
    coordinator.lightning_radius = 200
    coordinator.logger = logging.getLogger(__name__)
    coordinator.lightning_data = None
    coordinator.mareo_data = None
    return coordinator


class _SyntheticGeocoder:
    def reverse(self, location, **kwargs):
        return SimpleNamespace(address=f"Synthetic location {location}")


def test_lightning_success_payload_builds_structures(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator_private = cast(Any, coordinator)
    root = ET.fromstring(load_text_fixture("lightning_success.xml"))
    coordinator_private._FMIDataUpdateCoordinator__get_lightning_url = lambda: root
    monkeypatch.setattr(integration, "Nominatim", lambda **kwargs: _SyntheticGeocoder())

    coordinator_private._FMIDataUpdateCoordinator__update_lightning_strikes()

    lightning_data = coordinator.lightning_data
    assert lightning_data is not None
    assert len(lightning_data) == 2
    assert lightning_data[0].strikes == 2
    assert lightning_data[0].peak_current == -8.0
    assert lightning_data[0].location.startswith("Synthetic location")


def test_sea_level_success_payload_uses_only_supported_datum(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator_private = cast(Any, coordinator)
    content = load_text_fixture("sea_level_success.xml").encode()
    monkeypatch.setattr(
        integration.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(content=content),
    )

    coordinator_private._FMIDataUpdateCoordinator__update_mareo_data()

    mareo_data = coordinator.mareo_data
    assert mareo_data is not None
    values = mareo_data.get_values()
    assert [(item.time, item.sea_level) for item in values] == [
        ("2026-05-20 12:00", 12.5),
        ("2026-05-20 12:30", 13.0),
    ]


@pytest.mark.xfail(
    strict=True,
    reason="S09 hardening: malformed lightning payload must not escape the auxiliary update",
)
def test_malformed_lightning_payload_isolated_from_core_update(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator_private = cast(Any, coordinator)
    content = load_text_fixture("lightning_malformed.xml").encode()
    monkeypatch.setattr(
        integration.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(content=content),
    )

    coordinator_private._FMIDataUpdateCoordinator__get_lightning_url()

    assert coordinator.lightning_data is None


@pytest.mark.xfail(
    strict=True,
    reason="S09 hardening: malformed sea-level payload must not escape the auxiliary update",
)
def test_malformed_sea_level_payload_isolated_from_core_update(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator_private = cast(Any, coordinator)
    content = load_text_fixture("sea_level_malformed.xml").encode()
    monkeypatch.setattr(
        integration.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(content=content),
    )

    coordinator_private._FMIDataUpdateCoordinator__update_mareo_data()

    assert coordinator.mareo_data is None
