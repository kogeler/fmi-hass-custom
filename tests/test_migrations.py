# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Upgrade acceptance tests for v0.6.2 config entries and registries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import FMIDataUpdateCoordinator, async_migrate_entry
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import CONF_DAILY_MODE, CONF_ENTITY_IDENTITY, DOMAIN
from tests.helpers.fmi import forecast_from_fixture, load_json_fixture, weather_from_fixture


@dataclass(slots=True)
class LegacySnapshot:
    """Materialized v0.6.2 config and registry records."""

    entries: dict[str, MockConfigEntry]
    devices: dict[str, dr.DeviceEntry]
    entities: dict[str, er.RegistryEntry]


def _legacy_sensor_unique_id(identity: str, client_name: str, sensor_name: str) -> str:
    return f"{identity}_{client_name.replace(' ', '_')}_{sensor_name.replace(' ', '_')}"


def _create_v062_snapshot(
    hass: HomeAssistant,
    *,
    entry_keys: set[str] | None = None,
) -> LegacySnapshot:
    """Create registry records in the order that produced legacy numeric suffixes."""
    fixture = load_json_fixture("registry_v062.json")
    entry_specs = [
        spec for spec in fixture["entries"] if entry_keys is None or spec["key"] in entry_keys
    ]
    entries: dict[str, MockConfigEntry] = {}
    devices: dict[str, dr.DeviceEntry] = {}
    entities: dict[str, er.RegistryEntry] = {}

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for spec in entry_specs:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=spec["title"],
            unique_id=spec["unique_id"],
            data=spec["data"],
            options=spec["options"],
            version=spec["version"],
            minor_version=spec["minor_version"],
        )
        entry.add_to_hass(hass)
        entries[spec["key"]] = entry
        device_spec = spec["device"]
        devices[spec["key"]] = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_spec["identifier"])},
            name=device_spec["name"],
        )

    for spec in entry_specs:
        entry = entries[spec["key"]]
        identity = spec["device"]["identifier"]
        for sensor in spec["sensors"]:
            created = entity_registry.async_get_or_create(
                "sensor",
                DOMAIN,
                _legacy_sensor_unique_id(identity, spec["data"]["name"], sensor["name"]),
                suggested_object_id=sensor["created_entity_id"].split(".", 1)[1],
                config_entry=entry,
                original_name=sensor["name"],
            )
            assert created.entity_id == sensor["created_entity_id"]
            entities[sensor["key"]] = created
        for weather in spec["weather"]:
            created = entity_registry.async_get_or_create(
                "weather",
                DOMAIN,
                f"{identity}{weather['suffix']}",
                suggested_object_id=weather["created_entity_id"].split(".", 1)[1],
                config_entry=entry,
                device_id=devices[spec["key"]].id,
                original_name=weather["name"],
            )
            assert created.entity_id == weather["created_entity_id"]
            entities[weather["key"]] = created

    for spec in entry_specs:
        for entity_spec in (*spec["sensors"], *spec["weather"]):
            entity = entities[entity_spec["key"]]
            if entity.entity_id != entity_spec["entity_id"]:
                entity = entity_registry.async_update_entity(
                    entity.entity_id,
                    new_entity_id=entity_spec["entity_id"],
                )
                entities[entity_spec["key"]] = entity

    return LegacySnapshot(entries=entries, devices=devices, entities=entities)


def _patch_sources(
    monkeypatch,
    *,
    shared_place: str | None = None,
    include_oulu: bool = False,
) -> dict[str, AsyncMock]:
    """Provide deterministic location data for migration setup and reconfigure."""
    helsinki = weather_from_fixture("forecast_normal.json")
    base_forecast = forecast_from_fixture("forecast_normal.json")
    assert helsinki is not None
    locations = {
        (60.17, 24.94): helsinki._replace(place=shared_place or "Helsinki"),
        (61.5, 23.76): helsinki._replace(
            place=shared_place or "Tampere",
            lat=61.5,
            lon=23.76,
        ),
    }
    forecasts = {
        coordinates: base_forecast._replace(
            place=weather.place,
            lat=coordinates[0],
            lon=coordinates[1],
        )
        for coordinates, weather in locations.items()
    }
    if include_oulu:
        locations[(65.01, 25.47)] = helsinki._replace(
            place="Oulu",
            lat=65.01,
            lon=25.47,
        )
        forecasts[(65.01, 25.47)] = base_forecast._replace(
            place="Oulu",
            lat=65.01,
            lon=25.47,
        )

    mocks = {
        "weather": AsyncMock(side_effect=lambda lat, lon: locations[(lat, lon)]),
        "forecast": AsyncMock(side_effect=lambda lat, lon, *_args: forecasts[(lat, lon)]),
        "place_observation": AsyncMock(return_value=None),
    }
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", mocks["weather"])
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", mocks["forecast"])
    monkeypatch.setattr(fmi_client, "async_observation_by_place", mocks["place_observation"])
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        AsyncMock(return_value=None),
    )
    return mocks


async def _setup_snapshot(hass: HomeAssistant, snapshot: LegacySnapshot) -> None:
    for entry in snapshot.entries.values():
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entry_record(entry: MockConfigEntry) -> tuple[Any, ...]:
    return (
        entry.version,
        entry.minor_version,
        entry.unique_id,
        dict(entry.data),
        dict(entry.options),
    )


def _registry_records(
    hass: HomeAssistant,
    snapshot: LegacySnapshot,
) -> tuple[tuple[Any, ...], ...]:
    registry = er.async_get(hass)
    entry_ids = {entry.entry_id for entry in snapshot.entries.values()}
    return tuple(
        sorted(
            (
                entity.id,
                entity.entity_id,
                entity.unique_id,
                entity.config_entry_id,
                entity.device_id,
            )
            for entity in registry.entities.values()
            if entity.config_entry_id in entry_ids
        )
    )


def _registry_id(registry: er.EntityRegistry, entity_id: str) -> str:
    entry = registry.async_get(entity_id)
    assert entry is not None
    return entry.id


async def test_config_migration_is_registry_neutral_and_idempotent(
    hass: HomeAssistant,
) -> None:
    """Migrate serialized config metadata without touching entity/device records."""
    snapshot = _create_v062_snapshot(hass)
    entity_records = _registry_records(hass, snapshot)
    device_ids = {key: device.id for key, device in snapshot.devices.items()}

    for key, entry in snapshot.entries.items():
        original_options = dict(entry.options)
        assert await async_migrate_entry(hass, entry)
        assert entry.version == 2
        assert entry.minor_version == 1
        assert entry.unique_id == f"fmi:{entry.entry_id}"
        assert entry.data[CONF_ENTITY_IDENTITY] == snapshot.devices[key].identifiers.copy().pop()[1]
        assert dict(entry.options) == original_options

        first_result = _entry_record(entry)
        assert await async_migrate_entry(hass, entry)
        assert _entry_record(entry) == first_result

    assert _registry_records(hass, snapshot) == entity_records
    assert {key: device.id for key, device in snapshot.devices.items()} == device_ids


async def test_future_config_version_is_rejected_without_mutation(hass: HomeAssistant) -> None:
    """Refuse an unknown future schema instead of attempting a downgrade."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Future FMI",
        unique_id="future-id",
        data={"name": "FMI", "latitude": 60.17, "longitude": 24.94},
        options={"daily_mode": True},
        version=3,
        minor_version=7,
    )
    entry.add_to_hass(hass)
    original = _entry_record(entry)

    assert not await async_migrate_entry(hass, entry)
    assert _entry_record(entry) == original


async def test_registry_reconciliation_runs_after_separate_config_migration(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Apply registry changes only during setup of an already migrated config entry."""
    snapshot = _create_v062_snapshot(hass, entry_keys={"helsinki"})
    _patch_sources(monkeypatch)
    entry = snapshot.entries["helsinki"]
    original = snapshot.entities["helsinki_temperature"]
    original_registry = _registry_records(hass, snapshot)

    assert await async_migrate_entry(hass, entry)
    assert _registry_records(hass, snapshot) == original_registry
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    migrated = registry.async_get("sensor.helsinki_temperature")
    assert migrated is not None
    assert migrated.id == original.id
    assert migrated.unique_id == original.unique_id
    assert migrated.device_id == snapshot.devices["helsinki"].id
    assert registry.async_get("sensor.temperature") is None
    customized = registry.async_get("sensor.outdoor_humidity")
    assert customized is not None
    assert customized.id == snapshot.entities["helsinki_humidity"].id


async def test_combined_setup_preserves_registry_history_and_is_idempotent(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Reuse every legacy registry record while renaming only exact defaults."""
    snapshot = _create_v062_snapshot(hass)
    _patch_sources(monkeypatch)
    original_registry_ids = {key: entity.id for key, entity in snapshot.entities.items()}
    original_unique_ids = {key: entity.unique_id for key, entity in snapshot.entities.items()}

    await _setup_snapshot(hass, snapshot)

    registry = er.async_get(hass)
    assert (
        _registry_id(registry, "sensor.helsinki_temperature")
        == original_registry_ids["helsinki_temperature"]
    )
    assert (
        _registry_id(registry, "sensor.temperature_2")
        == original_registry_ids["tampere_temperature"]
    )
    assert (
        _registry_id(registry, "sensor.outdoor_humidity")
        == original_registry_ids["helsinki_humidity"]
    )
    assert (
        _registry_id(registry, "weather.helsinki_legacy_daily")
        == original_registry_ids["helsinki_daily"]
    )
    assert registry.async_get("sensor.temperature") is None

    entry_ids = {entry.entry_id for entry in snapshot.entries.values()}
    migrated_entities = {
        entity.id: entity
        for entity in registry.entities.values()
        if entity.config_entry_id in entry_ids
    }
    assert set(migrated_entities) == set(original_registry_ids.values())
    assert {entity.unique_id for entity in migrated_entities.values()} == set(
        original_unique_ids.values()
    )

    for key, registry_id in original_registry_ids.items():
        entity = migrated_entities[registry_id]
        assert entity.unique_id == original_unique_ids[key]
        entry_key = key.split("_", 1)[0]
        assert entity.device_id == snapshot.devices[entry_key].id

    device_registry = dr.async_get(hass)
    assert {
        device.id
        for entry in snapshot.entries.values()
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    } == {device.id for device in snapshot.devices.values()}
    helsinki_device = device_registry.async_get(snapshot.devices["helsinki"].id)
    tampere_device = device_registry.async_get(snapshot.devices["tampere"].id)
    assert helsinki_device is not None and helsinki_device.name == "Helsinki"
    assert tampere_device is not None and tampere_device.name == "Tampere"
    after_first_setup = _registry_records(hass, snapshot)

    for entry in snapshot.entries.values():
        assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _registry_records(hass, snapshot) == after_first_setup


async def test_ambiguous_suffix_is_preserved_for_same_place_multi_entry_history(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep indistinguishable suffixed IDs while maintaining separate identities/devices."""
    snapshot = _create_v062_snapshot(hass)
    _patch_sources(monkeypatch, shared_place="Shared Place")
    await _setup_snapshot(hass, snapshot)

    registry = er.async_get(hass)
    first = registry.async_get("sensor.shared_place_temperature")
    second = registry.async_get("sensor.temperature_2")
    assert first is not None and second is not None
    assert first.id == snapshot.entities["helsinki_temperature"].id
    assert second.id == snapshot.entities["tampere_temperature"].id
    assert first.unique_id != second.unique_id
    assert first.device_id == snapshot.devices["helsinki"].id
    assert second.device_id == snapshot.devices["tampere"].id
    assert first.device_id != second.device_id
    device_registry = dr.async_get(hass)
    helsinki_device = device_registry.async_get(snapshot.devices["helsinki"].id)
    tampere_device = device_registry.async_get(snapshot.devices["tampere"].id)
    assert helsinki_device is not None and helsinki_device.name == "Shared Place"
    assert tampere_device is not None and tampere_device.name == "Shared Place"
    assert registry.async_get("weather.helsinki") is not None
    assert registry.async_get("weather.tampere") is not None


async def test_duplicate_coordinate_policy_is_stable_across_migration(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Reject an occupied location before and after its owner is migrated."""
    snapshot = _create_v062_snapshot(hass)
    validate = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)

    for migrate_first in (False, True):
        if migrate_first:
            for entry in snapshot.entries.values():
                assert await async_migrate_entry(hass, entry)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"name": "FMI", "latitude": 60.17, "longitude": 24.94},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    validate.assert_not_awaited()


async def test_reconfigure_after_migration_preserves_all_registry_identity(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Move a migrated entry without recreating legacy, custom, weather, or daily records."""
    snapshot = _create_v062_snapshot(hass)
    _patch_sources(monkeypatch, include_oulu=True)
    await _setup_snapshot(hass, snapshot)
    entry = snapshot.entries["helsinki"]
    original_identity = entry.data[CONF_ENTITY_IDENTITY]
    original_records = _registry_records(hass, snapshot)
    original_device_id = snapshot.devices["helsinki"].id

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LATITUDE: 65.01, CONF_LONGITUDE: 25.47},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data[CONF_ENTITY_IDENTITY] == original_identity
    assert entry.data[CONF_LATITUDE] == 65.01
    assert entry.data[CONF_LONGITUDE] == 25.47
    assert entry.title == "Oulu"
    assert _registry_records(hass, snapshot) == original_records
    device = dr.async_get(hass).async_get(original_device_id)
    assert device is not None and device.name == "Oulu"
    assert er.async_get(hass).async_get("sensor.helsinki_temperature") is not None
    assert er.async_get(hass).async_get("sensor.oulu_temperature") is None
    assert er.async_get(hass).async_get("sensor.outdoor_humidity") is not None
    assert er.async_get(hass).async_get("weather.helsinki_legacy_daily") is not None


async def test_legacy_daily_entity_survives_disable_and_reenable(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Retain the optional daily registry/custom ID across option-driven reloads."""
    snapshot = _create_v062_snapshot(hass)
    _patch_sources(monkeypatch)
    await _setup_snapshot(hass, snapshot)
    entry = snapshot.entries["helsinki"]
    registry = er.async_get(hass)
    original = registry.async_get("weather.helsinki_legacy_daily")
    assert original is not None
    original_id = original.id
    original_unique_id = original.unique_id
    assert hass.states.get(original.entity_id) is not None

    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_DAILY_MODE: False},
    )
    await hass.async_block_till_done()
    disabled = registry.async_get("weather.helsinki_legacy_daily")
    assert disabled is not None
    assert disabled.id == original_id
    assert disabled.unique_id == original_unique_id
    disabled_state = hass.states.get(disabled.entity_id)
    assert disabled_state is not None and disabled_state.state == STATE_UNAVAILABLE

    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_DAILY_MODE: True},
    )
    await hass.async_block_till_done()
    restored = registry.async_get("weather.helsinki_legacy_daily")
    assert restored is not None
    assert restored.id == original_id
    assert restored.unique_id == original_unique_id
    assert hass.states.get(restored.entity_id) is not None
