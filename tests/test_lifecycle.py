# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Home Assistant-level setup, entity, options, and lifecycle contracts for FMI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fmi_weather_client import models
from fmi_weather_client.errors import ClientError
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import (
    FMIDataUpdateCoordinator,
    FMILightningStruct,
    FMIMareoStruct,
    async_unload_entry,
)
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import (
    BEST_CONDITION_NOT_AVAIL,
    CONF_DAILY_MODE,
    CONF_ENTITY_IDENTITY,
    CONF_FORECAST_DAYS,
    CONF_LIGHTNING,
    CONF_OBSERVATION_STATION,
    COORDINATOR,
    COORDINATOR_OBSERVATION,
    DOMAIN,
)
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture


def _entry(
    hass: HomeAssistant,
    *,
    title: str = "Synthetic Helsinki",
    latitude: float = 60.17,
    longitude: float = 24.94,
    entry_id: str | None = None,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Add a current-version synthetic entry with independent stable identity."""
    identity = f"identity:{entry_id or title}:{latitude}:{longitude}"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        entry_id=entry_id,
        unique_id=f"fmi:{entry_id or title}:{latitude}:{longitude}",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
            CONF_ENTITY_IDENTITY: identity,
        },
        options=options or {},
        version=2,
    )
    entry.add_to_hass(hass)
    return entry


def _patch_sources(
    monkeypatch,
    *,
    weather: models.Weather | None = None,
    forecast: models.Forecast | None = None,
    observation: models.Weather | None = None,
) -> dict[str, AsyncMock]:
    """Install deterministic FMI source mocks and an empty optional source."""
    mocks = {
        "weather": AsyncMock(return_value=weather),
        "forecast": AsyncMock(return_value=forecast),
        "place_observation": AsyncMock(return_value=None),
        "station_observation": AsyncMock(return_value=observation),
    }
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", mocks["weather"])
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", mocks["forecast"])
    monkeypatch.setattr(fmi_client, "async_observation_by_place", mocks["place_observation"])
    monkeypatch.setattr(
        fmi_client,
        "async_observation_by_station_id",
        mocks["station_observation"],
    )

    async def empty_sea_level(self: FMIDataUpdateCoordinator) -> None:
        self.mareo_data = None

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        empty_sea_level,
    )
    return mocks


def _patch_optional_success(monkeypatch) -> None:
    """Return deterministic lightning and sea-level data without network access."""
    strike_time = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)

    async def update_lightning(self: FMIDataUpdateCoordinator) -> None:
        self.lightning_data = [
            FMILightningStruct(
                time=strike_time,
                location="Synthetic lightning location",
                distance=12.5,
                strikes=2,
                peak_current=-8.0,
                cloud_cover=40.0,
                ellipse_major=1.2,
            ),
            FMILightningStruct(
                time=strike_time,
                location="Second synthetic location",
                distance=18.0,
                strikes=1,
                peak_current=-4.0,
                cloud_cover=30.0,
                ellipse_major=0.8,
            ),
        ]

    async def update_sea_level(self: FMIDataUpdateCoordinator) -> None:
        mareo = FMIMareoStruct()
        mareo.append_values(strike_time, 12.5)
        mareo.append_values(strike_time.replace(hour=13), 13.0)
        self.mareo_data = mareo

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_lightning_strikes",
        update_lightning,
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        update_sea_level,
    )


async def _forecast_service(
    hass: HomeAssistant,
    entity_id: str,
    forecast_type: str,
) -> list[dict[str, Any]]:
    """Request converted forecasts through Home Assistant's public entity service."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": entity_id, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    entity_response = response[entity_id]
    assert isinstance(entity_response, dict)
    forecast = entity_response["forecast"]
    assert isinstance(forecast, list)
    assert all(isinstance(item, dict) for item in forecast)
    return cast(list[dict[str, Any]], forecast)


async def _configure_options(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    **updates: Any,
) -> None:
    """Submit a complete options form through Home Assistant's public flow API."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert schema is not None
    options = schema({})
    options.update(updates)
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_public_entity_and_forecast_contracts(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Expose every supported entity family through Home Assistant APIs."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    observation = weather_from_fixture("observation.json", "observation")
    assert weather is not None and observation is not None
    _patch_sources(
        monkeypatch,
        weather=weather,
        forecast=forecast,
        observation=observation,
    )
    _patch_optional_success(monkeypatch)
    entry = _entry(
        hass,
        options={
            CONF_DAILY_MODE: True,
            CONF_LIGHTNING: True,
            CONF_OBSERVATION_STATION: 101004,
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    weather_states = {
        state.attributes.get("friendly_name"): state
        for state in hass.states.async_all(WEATHER_DOMAIN)
    }
    assert {
        "Helsinki",
        "Helsinki (daily)",
        "Helsinki Kaisaniemi Observation",
    } <= weather_states.keys()
    current = weather_states["Helsinki"]
    assert current.state == "partlycloudy"
    assert current.attributes["temperature"] == -4.0
    assert current.attributes["temperature_unit"] == "°C"
    assert current.attributes["pressure_unit"] == "hPa"
    observation_state = weather_states["Helsinki Kaisaniemi Observation"]
    assert observation_state.state == "partlycloudy"
    assert observation_state.attributes["temperature"] == 6.5
    assert observation_state.attributes["supported_features"] == 0

    hourly = await _forecast_service(hass, current.entity_id, "hourly")
    daily = await _forecast_service(hass, current.entity_id, "daily")
    assert len(hourly) == 49
    assert len(daily) == 3
    assert hourly[0]["datetime"].endswith("+00:00")
    assert daily[0]["datetime"].endswith("+00:00")
    assert hourly[0]["temperature"] == -5.0
    assert daily[0]["templow"] == -5.0

    temperature = hass.states.get("sensor.helsinki_temperature")
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    sea_level = hass.states.get("sensor.helsinki_sea_level")
    assert temperature is not None and temperature.state == "-4.0"
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert lightning is not None and lightning.state == "Synthetic lightning location"
    assert lightning.attributes["distance"] == 12.5
    assert len(lightning.attributes["OBSERVATIONS"]) == 1
    assert sea_level is not None and sea_level.state == "12.5"
    assert sea_level.attributes["unit_of_measurement"] == "cm"
    assert len(sea_level.attributes["FORECASTS"]) == 1

    registry = er.async_get(hass)
    temperature_entry = registry.async_get(temperature.entity_id)
    assert temperature_entry is not None and temperature_entry.device_id is not None
    assert temperature_entry.config_entry_id == entry.entry_id
    device = dr.async_get(hass).async_get(temperature_entry.device_id)
    assert device is not None
    assert device.name == "Helsinki"
    assert device.manufacturer == "Finnish Meteorological Institute"


async def test_options_reload_adds_and_removes_optional_entities_once(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Reload exactly once per option change without duplicate entities or listeners."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    observation = weather_from_fixture("observation.json", "observation")
    assert weather is not None and observation is not None
    _patch_sources(
        monkeypatch,
        weather=weather,
        forecast=forecast,
        observation=observation,
    )
    _patch_optional_success(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.update_listeners) == 1
    assert hass.states.get("sensor.helsinki_lightning_strikes") is None
    assert hass.states.get("weather.helsinki_daily") is None
    old_coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    registry = er.async_get(hass)
    main_registry_entry = registry.async_get("weather.helsinki")
    assert main_registry_entry is not None

    await _configure_options(
        hass,
        entry,
        **{
            CONF_DAILY_MODE: True,
            CONF_LIGHTNING: True,
            CONF_OBSERVATION_STATION: 101004,
        },
    )

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.update_listeners) == 1
    assert not old_coordinator._listeners
    assert hass.states.get("sensor.helsinki_lightning_strikes") is not None
    assert hass.states.get("weather.helsinki_daily") is not None
    assert hass.states.get("weather.helsinki_kaisaniemi_observation") is not None
    main_after_enable = registry.async_get("weather.helsinki")
    assert main_after_enable is not None
    assert main_after_enable.id == main_registry_entry.id
    assert (
        len([state for state in hass.states.async_all() if state.entity_id == "weather.helsinki"])
        == 1
    )
    enabled_coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    await _configure_options(
        hass,
        entry,
        **{
            CONF_DAILY_MODE: False,
            CONF_LIGHTNING: False,
            CONF_OBSERVATION_STATION: 0,
        },
    )

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.update_listeners) == 1
    assert not enabled_coordinator._listeners
    for entity_id in (
        "sensor.helsinki_lightning_strikes",
        "weather.helsinki_daily",
        "weather.helsinki_kaisaniemi_observation",
    ):
        state = hass.states.get(entity_id)
        assert state is not None and state.state == STATE_UNAVAILABLE
    main_after_disable = registry.async_get("weather.helsinki")
    assert main_after_disable is not None
    assert main_after_disable.id == main_registry_entry.id


async def test_reload_unload_and_remove_do_not_duplicate_lifecycle_state(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Preserve registry identity while cleaning listeners and states at each transition."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    temperature = registry.async_get("sensor.helsinki_temperature")
    assert temperature is not None
    registry_id = temperature.id
    old_coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    assert len(entry.update_listeners) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not old_coordinator._listeners
    assert len(entry.update_listeners) == 1
    reloaded_temperature = registry.async_get("sensor.helsinki_temperature")
    assert reloaded_temperature is not None
    assert reloaded_temperature.id == registry_id
    assert len(hass.states.async_all("sensor")) == len(
        {state.entity_id for state in hass.states.async_all("sensor")}
    )
    reloaded_coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
    assert not reloaded_coordinator._listeners
    assert not entry.update_listeners
    unloaded_state = hass.states.get("sensor.helsinki_temperature")
    assert unloaded_state is not None and unloaded_state.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.update_listeners) == 1
    restored_temperature = registry.async_get("sensor.helsinki_temperature")
    assert restored_temperature is not None
    assert restored_temperature.id == registry_id

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert entry.entry_id not in hass.data[DOMAIN]
    assert hass.states.get("sensor.helsinki_temperature") is None


async def test_failed_platform_unload_retains_loaded_entry_data(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep integration data and update listener when a platform refuses to unload."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    original_unload = hass.config_entries.async_unload_platforms
    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    )

    assert not await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert hass.data[DOMAIN][entry.entry_id][COORDINATOR] is coordinator
    assert len(entry.update_listeners) == 1

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", original_unload)
    assert await async_unload_entry(hass, entry)
    await hass.async_block_till_done()


@pytest.mark.parametrize("station_failure", [None, TimeoutError("Synthetic timeout")])
async def test_observation_no_data_or_timeout_recovers_through_weather_entity(
    hass: HomeAssistant,
    monkeypatch,
    station_failure: Exception | None,
) -> None:
    """Keep the entry loaded while an unavailable observation entity later recovers."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    observation = weather_from_fixture("observation.json", "observation")
    assert weather is not None and observation is not None
    mocks = _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    if station_failure is None:
        mocks["station_observation"].side_effect = [None, observation]
    else:
        mocks["station_observation"].side_effect = [station_failure, observation]
    entry = _entry(hass, options={CONF_OBSERVATION_STATION: 101004})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    observation_state = hass.states.get("weather.fmi_observation")
    assert observation_state is not None
    assert observation_state.state == STATE_UNAVAILABLE
    observation_coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_OBSERVATION]

    await observation_coordinator.async_refresh()
    await hass.async_block_till_done()

    observation_state = hass.states.get("weather.fmi_observation")
    assert observation_state is not None
    assert observation_state.state == "partlycloudy"
    assert observation_state.attributes["temperature"] == 6.5


@pytest.mark.parametrize("forecast_mode", ["disabled", "empty"])
async def test_disabled_or_empty_forecast_exposes_empty_public_result(
    hass: HomeAssistant,
    monkeypatch,
    forecast_mode: str,
) -> None:
    """Keep current weather available while the public forecast result is empty."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    if forecast_mode == "disabled":
        forecast = forecast_from_fixture("forecast_normal.json")
        options = {CONF_FORECAST_DAYS: 0}
    else:
        forecast = models.Forecast(place="Helsinki", lat=60.17, lon=24.94, forecasts=[])
        options = {}
    mocks = _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    entry = _entry(hass, options=options)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.helsinki")
    assert state is not None and state.state != STATE_UNAVAILABLE
    assert await _forecast_service(hass, state.entity_id, "hourly") == []
    if forecast_mode == "disabled":
        mocks["forecast"].assert_not_awaited()
    else:
        mocks["forecast"].assert_awaited_once()


async def test_empty_entry_title_does_not_attempt_place_fallback(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Enter setup retry without a meaningless place lookup when no title exists."""
    source_error = ClientError(400, "Synthetic current failure")
    mocks = _patch_sources(monkeypatch, forecast=forecast_from_fixture("forecast_normal.json"))
    mocks["weather"].side_effect = source_error
    entry = _entry(hass, title="")

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mocks["place_observation"].assert_not_awaited()
    entry.async_cancel_retry_setup()


async def test_two_locations_fail_and_recover_independently(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Isolate one location's outage, recovery, and unload from another entry."""
    helsinki = weather_from_fixture("forecast_normal.json")
    helsinki_forecast = forecast_from_fixture("forecast_normal.json")
    assert helsinki is not None
    tampere = helsinki._replace(place="Tampere", lat=61.5, lon=23.76)
    tampere_forecast = helsinki_forecast._replace(place="Tampere", lat=61.5, lon=23.76)
    current_by_location = {(60.17, 24.94): helsinki, (61.5, 23.76): tampere}
    forecast_by_location = {
        (60.17, 24.94): helsinki_forecast,
        (61.5, 23.76): tampere_forecast,
    }
    failed_locations: set[tuple[float, float]] = set()

    async def current(latitude: float, longitude: float):
        location = (latitude, longitude)
        if location in failed_locations:
            raise ClientError(400, "Synthetic location outage")
        return current_by_location[location]

    async def forecast(latitude: float, longitude: float, *_args):
        return forecast_by_location[(latitude, longitude)]

    async def place_observation(place: str):
        if place == "Synthetic Tampere" and (61.5, 23.76) in failed_locations:
            raise ClientError(400, "Synthetic location outage")
        return None

    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", current)
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", forecast)
    monkeypatch.setattr(fmi_client, "async_observation_by_place", place_observation)

    async def empty_sea_level(self: FMIDataUpdateCoordinator) -> None:
        self.mareo_data = None

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        empty_sea_level,
    )
    helsinki_entry = _entry(hass, entry_id="helsinki-entry")
    tampere_entry = _entry(
        hass,
        title="Synthetic Tampere",
        latitude=61.5,
        longitude=23.76,
        entry_id="tampere-entry",
    )

    for entry in (helsinki_entry, tampere_entry):
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    helsinki_state = hass.states.get("sensor.helsinki_temperature")
    tampere_state = hass.states.get("sensor.tampere_temperature")
    assert helsinki_state is not None and helsinki_state.state != STATE_UNAVAILABLE
    assert tampere_state is not None and tampere_state.state != STATE_UNAVAILABLE
    tampere_coordinator = hass.data[DOMAIN][tampere_entry.entry_id][COORDINATOR]

    failed_locations.add((61.5, 23.76))
    await tampere_coordinator.async_refresh()
    await hass.async_block_till_done()

    helsinki_state = hass.states.get("sensor.helsinki_temperature")
    tampere_state = hass.states.get("sensor.tampere_temperature")
    assert helsinki_state is not None and helsinki_state.state != STATE_UNAVAILABLE
    assert tampere_state is not None and tampere_state.state == STATE_UNAVAILABLE

    failed_locations.clear()
    await tampere_coordinator.async_refresh()
    await hass.async_block_till_done()

    tampere_state = hass.states.get("sensor.tampere_temperature")
    assert tampere_state is not None and tampere_state.state != STATE_UNAVAILABLE
    assert await hass.config_entries.async_unload(tampere_entry.entry_id)
    await hass.async_block_till_done()
    tampere_state = hass.states.get("sensor.tampere_temperature")
    assert tampere_state is not None and tampere_state.state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.helsinki_temperature") is not None


async def test_wind_direction_updates_cover_public_compass_states(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Publish every compass bucket and invalid input through the sensor state API."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    mocks = _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    for degrees, expected in [
        (-1.0, STATE_UNAVAILABLE),
        (0.0, "N"),
        (45.0, "NE"),
        (90.0, "E"),
        (135.0, "SE"),
        (180.0, "S"),
        (225.0, "SW"),
        (270.0, "W"),
        (315.0, "NW"),
    ]:
        mocks["weather"].return_value = weather._replace(
            data=weather.data._replace(wind_direction=models.Value(degrees, "°"))
        )
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get("sensor.helsinki_wind_direction")
        assert state is not None
        assert state.state == expected


async def test_best_condition_rejects_each_out_of_range_forecast(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Exercise wind, humidity, and precipitation rejection through first refresh."""
    weather = weather_from_fixture("forecast_normal.json")
    source_forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    current_time = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
    invalid_samples = [
        source_forecast.forecasts[0]._replace(
            time=current_time,
            temperature=models.Value(20.0, "°C"),
            wind_speed=models.Value(100.0, "m/s"),
        ),
        source_forecast.forecasts[1]._replace(
            time=current_time.replace(hour=13),
            temperature=models.Value(20.0, "°C"),
            wind_speed=models.Value(4.0, "m/s"),
            humidity=models.Value(101.0, "%"),
        ),
        source_forecast.forecasts[2]._replace(
            time=current_time.replace(hour=14),
            temperature=models.Value(20.0, "°C"),
            wind_speed=models.Value(4.0, "m/s"),
            humidity=models.Value(50.0, "%"),
            precipitation_amount=models.Value(100.0, "mm/h"),
        ),
    ]
    forecast = source_forecast._replace(forecasts=invalid_samples)
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    monkeypatch.setattr(
        "custom_components.fmi.dt_util.now",
        lambda: current_time,
    )
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    assert coordinator.best_state == BEST_CONDITION_NOT_AVAIL
