# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/SENSORS.md, docs/contracts/WARNINGS.md

"""Presence of official active warnings, independent of primary weather."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FMIConfigEntry
from .warnings_entity import FMIWarningEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: FMIConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add a stable binary entity only when warnings are enabled."""
    _ = hass
    runtime = entry.runtime_data
    if runtime.warnings_coordinator is not None:
        async_add_entities(
            [
                FMIWeatherWarningBinarySensor(
                    runtime.warnings_coordinator,
                    runtime.coordinator.unique_id,
                    runtime.coordinator.get_current_place() or entry.data[CONF_NAME],
                    "weather_warning",
                )
            ]
        )


class FMIWeatherWarningBinarySensor(FMIWarningEntity, BinarySensorEntity):
    """Report warning presence without labeling an all-clear as safe weather."""

    _attr_translation_key = "weather_warning"
    _attr_icon = "mdi:weather-lightning"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return bool(data.active) if data is not None else None
