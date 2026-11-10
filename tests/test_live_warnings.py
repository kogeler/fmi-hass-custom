# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Bounded real CAP locale probes using production coordinators."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant

from custom_components.fmi import warnings_coordinator
from custom_components.fmi.warnings_coordinator import FMIWarningsCoordinator
from tests.helpers.live_budget import LiveRequestBudget
from tests.helpers.live_network import live_network
from tests.helpers.warning_live import record_live_structure, validate_live_warning_recognition

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("disable_mock_zeroconf_resolver")]


@pytest.fixture(autouse=True)
def enable_live_network() -> Generator[None]:
    """Undo the HA test plugin's per-test network guard only for live tests."""
    with live_network():
        yield


@pytest.mark.parametrize("language", ["fi", "sv"])
async def test_live_warning_locale_uses_production_coordinator(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    """Allow empty local matches while requiring usable real publications in every locale."""
    observed: dict[str, int] = {}
    fetch = warnings_coordinator.async_fetch_warning_payload
    root = Path(os.environ["FMI_LIVE_BUDGET_DIR"])

    async def traced_fetch(session, selected):
        payload = await fetch(session, selected)
        observed.update(
            await hass.async_add_executor_job(validate_live_warning_recognition, payload, selected)
        )
        await hass.async_add_executor_job(record_live_structure, root, selected, observed)
        return payload

    monkeypatch.setattr(warnings_coordinator, "async_fetch_warning_payload", traced_fetch)
    coordinator = FMIWarningsCoordinator(hass, None, 60.17, 24.94, language)
    try:
        budget = LiveRequestBudget(root)
        async with budget.request():
            await coordinator.async_refresh()
        assert coordinator.last_update_success, (
            f"CAP production failure: {coordinator.last_exception!s}; structure={observed}"
        )
        assert coordinator.data is not None
        attributes = coordinator.data.attributes()
        assert attributes["requested_language"] == language
        assert coordinator.data.updated.tzinfo is not None
        assert isinstance(attributes["warnings"], list)
        assert isinstance(attributes["upcoming_warnings"], list)
        for item in (*coordinator.data.active, *coordinator.data.upcoming):
            assert item.language.split("-")[0] in {language, "en", "fi", "sv"}
            assert item.expires > item.onset
    finally:
        await coordinator.async_shutdown()
