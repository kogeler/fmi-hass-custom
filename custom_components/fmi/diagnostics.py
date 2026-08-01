# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Sanitized diagnostics for the FMI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import FMIConfigEntry, FMIDataUpdateCoordinator, const

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE, const.CONF_ENTITY_IDENTITY}


def _coordinator_diagnostics(coordinator: FMIDataUpdateCoordinator) -> dict[str, Any]:
    """Return source health and cadence without locations or weather payloads."""
    interval = coordinator.update_interval
    return {
        "last_update_success": coordinator.last_update_success,
        "poll_interval_seconds": interval.total_seconds() if interval is not None else None,
        "source_availability": coordinator.source_availability,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: FMIConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for one config entry with private location data redacted."""
    _ = hass
    observation = entry.runtime_data.observation_coordinator
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
            "version": entry.version,
            "minor_version": entry.minor_version,
        },
        "coordinators": {
            "primary": _coordinator_diagnostics(entry.runtime_data.coordinator),
            "observation": (
                _coordinator_diagnostics(observation) if observation is not None else None
            ),
        },
    }
