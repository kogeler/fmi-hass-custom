# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Home Assistant regressions for wind gusts and sensor location grouping."""

import math
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fmi_weather_client.errors import ClientError
from fmi_weather_client.models import Value
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    STATE_UNAVAILABLE,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import FMIDataUpdateCoordinator
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import COORDINATOR, DOMAIN
from custom_components.fmi.sensor import (
    LIGHTNING_DESCRIPTION,
    SEA_LEVEL_DESCRIPTION,
    SENSOR_DESCRIPTIONS,
    FMIBestConditionSensor,
)
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture


def _entry(
    hass: HomeAssistant,
    *,
    latitude: float = 60.17,
    longitude: float = 24.94,
    title: str = "Synthetic Helsinki",
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=f"{latitude}_{longitude}",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _patch_sources(monkeypatch, weather) -> dict[str, AsyncMock]:
    forecast = forecast_from_fixture("forecast_normal.json")
    mocks = {
        "weather": AsyncMock(return_value=weather),
        "forecast": AsyncMock(return_value=forecast),
        "place_observation": AsyncMock(return_value=None),
    }
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", mocks["weather"])
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", mocks["forecast"])
    monkeypatch.setattr(fmi_client, "async_observation_by_place", mocks["place_observation"])
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__update_mareo_data",
        lambda self: None,
    )
    return mocks


def _legacy_temperature_unique_id(latitude: float = 60.17, longitude: float = 24.94) -> str:
    return f"{latitude}:{longitude}_FMI_Temperature"


async def test_hourly_maximum_gust_restores_sensor(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Use the forecast producer's hourly maximum when WindGust is absent."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    weather = weather._replace(
        data=weather.data._replace(
            wind_gust=Value(None, "m/s"),
            wind_max=Value(9.4, "m/s"),
        )
    )
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.helsinki_wind_gust")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "33.84"
    assert state.attributes["unit_of_measurement"] == UnitOfSpeed.KILOMETERS_PER_HOUR


async def test_fresh_sensors_use_location_device_context(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Generate location-aware IDs and group sensors under the location device."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.helsinki_temperature")
    assert state is not None
    assert state.attributes["friendly_name"] == "Helsinki Temperature"

    entity_entry = er.async_get(hass).async_get(state.entity_id)
    assert entity_entry is not None
    assert entity_entry.has_entity_name
    assert entity_entry.device_id is not None
    device_entry = dr.async_get(hass).async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.name == "Helsinki"
    assert device_entry.identifiers == {(DOMAIN, "60.17:24.94")}


@pytest.mark.parametrize(
    ("wind_gust", "wind_max", "expected"),
    [
        (7.8, 9.4, 7.8),
        (None, 9.4, 9.4),
        (math.nan, 9.4, 9.4),
        (math.inf, 9.4, 9.4),
        (0.0, 9.4, 0.0),
        (None, None, None),
        (math.nan, math.nan, None),
        (math.inf, -math.inf, None),
    ],
)
def test_wind_gust_finite_precedence_and_missing_values(
    wind_gust: float | None,
    wind_max: float | None,
    expected: float | None,
) -> None:
    """Prefer finite WindGust, retain zero, and then use the hourly fallback."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    source_data = weather.data._replace(
        wind_gust=Value(wind_gust, "m/s"),
        wind_max=Value(wind_max, "m/s"),
    )
    sensor = object.__new__(FMIBestConditionSensor)
    sensor._attr_native_value = None

    cast(Any, sensor)._FMIBestConditionSensor__convert_float(
        source_data,
        "wind_gust",
        "wind_max",
    )

    assert sensor._attr_native_value == expected


async def test_two_locations_create_distinct_devices_and_sensor_ids(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep identical sensor types separate for two configured locations."""
    helsinki = weather_from_fixture("forecast_normal.json")
    assert helsinki is not None
    tampere = helsinki._replace(place="Tampere", lat=61.5, lon=23.76)
    weather_by_location = {(60.17, 24.94): helsinki, (61.5, 23.76): tampere}
    forecast = forecast_from_fixture("forecast_normal.json")
    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        AsyncMock(side_effect=lambda lat, lon: weather_by_location[(lat, lon)]),
    )
    monkeypatch.setattr(
        fmi_client,
        "async_forecast_by_coordinates",
        AsyncMock(return_value=forecast),
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__update_mareo_data",
        lambda self: None,
    )
    entries = [
        _entry(hass),
        _entry(hass, latitude=61.5, longitude=23.76, title="Synthetic Tampere"),
    ]

    for entry in entries:
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    helsinki_state = hass.states.get("sensor.helsinki_temperature")
    tampere_state = hass.states.get("sensor.tampere_temperature")
    assert helsinki_state is not None
    assert tampere_state is not None
    registry = er.async_get(hass)
    helsinki_entry = registry.async_get(helsinki_state.entity_id)
    tampere_entry = registry.async_get(tampere_state.entity_id)
    assert helsinki_entry is not None and tampere_entry is not None
    assert helsinki_entry.unique_id != tampere_entry.unique_id
    assert helsinki_entry.device_id != tampere_entry.device_id


async def test_non_ascii_punctuated_location_is_preserved_and_slugged(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep the display name while generating a valid location-aware entity ID."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    place = "Jyväskylä, Keskusta"
    weather = weather._replace(place=place)
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass, title="Synthetic Jyväskylä")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"sensor.{slugify(f'{place} Temperature')}"
    state = hass.states.get(entity_id)
    assert state is not None
    entity_entry = er.async_get(hass).async_get(entity_id)
    assert entity_entry is not None and entity_entry.device_id is not None
    device = dr.async_get(hass).async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == place


async def test_exact_legacy_generated_entity_id_is_migrated(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Rename the exact v0.6.2 default without recreating its registry entry."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        _legacy_temperature_unique_id(),
        suggested_object_id="temperature",
        config_entry=entry,
        original_name="Temperature",
    )
    legacy_registry_id = legacy.id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated = registry.async_get("sensor.helsinki_temperature")
    assert migrated is not None
    assert migrated.id == legacy_registry_id
    assert registry.async_get("sensor.temperature") is None


async def test_user_customized_entity_id_is_preserved(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Never rename a registry ID that differs from the exact legacy default."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        _legacy_temperature_unique_id(),
        suggested_object_id="temperature",
        config_entry=entry,
        original_name="Temperature",
    )
    registry.async_update_entity(
        legacy.entity_id, new_entity_id="sensor.outdoor_custom_temperature"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    customized = registry.async_get("sensor.outdoor_custom_temperature")
    assert customized is not None
    assert customized.id == legacy.id
    assert registry.async_get("sensor.helsinki_temperature") is None


async def test_legacy_entity_id_migration_skips_target_collision(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep both entries intact when the location-aware target is occupied."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather)
    entry = _entry(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        _legacy_temperature_unique_id(),
        suggested_object_id="temperature",
        config_entry=entry,
        original_name="Temperature",
    )
    collision = registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "synthetic_collision",
        suggested_object_id="helsinki_temperature",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_after_setup = registry.async_get("sensor.temperature")
    collision_after_setup = registry.async_get("sensor.helsinki_temperature")
    assert legacy_after_setup is not None
    assert collision_after_setup is not None
    assert legacy_after_setup.id == legacy.id
    assert collision_after_setup.id == collision.id


async def test_sensor_availability_recovers_with_coordinator(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Expose unavailable during a current-source outage and recover in place."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    source_error = ClientError(400, "Synthetic current failure")
    mocks = _patch_sources(monkeypatch, weather)
    mocks["weather"].side_effect = [weather, source_error, weather]
    mocks["place_observation"].side_effect = source_error
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    state = hass.states.get("sensor.helsinki_temperature")
    assert state is not None and state.state != STATE_UNAVAILABLE

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.helsinki_temperature")
    assert state is not None and state.state == STATE_UNAVAILABLE

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.helsinki_temperature")
    assert state is not None and state.state != STATE_UNAVAILABLE


def test_all_sensor_descriptions_have_current_units_and_types() -> None:
    """Keep every existing sensor on an explicit Home Assistant metadata contract."""
    descriptions = {
        item.key: item
        for item in (*SENSOR_DESCRIPTIONS, LIGHTNING_DESCRIPTION, SEA_LEVEL_DESCRIPTION)
    }

    assert descriptions["temperature"].device_class == "temperature"
    assert descriptions["temperature"].state_class == "measurement"
    assert descriptions["wind_speed"].device_class == "wind_speed"
    assert descriptions["wind_gust"].native_unit_of_measurement == "m/s"
    assert descriptions["humidity"].device_class == "humidity"
    assert descriptions["rain"].device_class == "precipitation_intensity"
    assert descriptions["cloud_coverage"].native_unit_of_measurement == "%"
    assert descriptions["sea_level"].device_class == "distance"
    assert descriptions["sea_level"].native_unit_of_measurement == "cm"
    assert descriptions["place"].device_class is None
    assert descriptions["condition"].state_class is None
    assert descriptions["wind_direction"].native_unit_of_measurement is None
    assert descriptions["forecast_time"].device_class is None
    assert descriptions["best_time_of_day"].device_class is None
    assert descriptions["lightning_strikes"].native_unit_of_measurement is None
