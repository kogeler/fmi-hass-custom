# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/MIGRATIONS.md, docs/contracts/SENSORS.md

"""Shared entry identity and availability for the warning platforms."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .warnings_coordinator import FMIWarningsCoordinator


class FMIWarningEntity(CoordinatorEntity[FMIWarningsCoordinator]):
    """Attach additive warning entities to the existing immutable location device."""

    _attr_has_entity_name = True
    _attr_attribution = const.ATTRIBUTION
    _unrecorded_attributes = frozenset({"warnings", "upcoming_warnings"})

    def __init__(
        self, coordinator: FMIWarningsCoordinator, identity: str, device_name: str, suffix: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{identity}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, identity)},
            name=device_name,
            manufacturer=const.MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        # A transient retrieval failure keeps the held snapshot under WRN-004.
        return self.coordinator.data is not None
