# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Home Assistant-level setup, entity, options, and lifecycle contracts for FMI."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
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
from homeassistant.helpers import translation
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import (
    FMIDataUpdateCoordinator,
    FMILightningStruct,
    FMIMareoStruct,
    OptionalSourceError,
    async_unload_entry,
)
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import (
    BEST_CONDITION_NO_SUITABLE,
    BEST_CONDITION_NOT_AVAIL,
    CONF_DAILY_MODE,
    CONF_ENTITY_IDENTITY,
    CONF_FORECAST_DAYS,
    CONF_LIGHTNING,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_OBSERVATION_STATION,
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
    weather_result = (
        fmi_client.CurrentWeatherResult(
            weather,
            fmi_client.ForecastProbabilities(0.0, 100.0),
        )
        if weather is not None
        else None
    )
    forecast_result = (
        fmi_client.ForecastResult(
            forecast,
            MappingProxyType(
                {
                    sample.time.astimezone(UTC): fmi_client.ForecastProbabilities(25.0, 5.0)
                    for sample in forecast.forecasts
                }
            ),
        )
        if forecast is not None
        else None
    )
    mocks = {
        "weather": AsyncMock(return_value=weather_result),
        "forecast": AsyncMock(return_value=forecast_result),
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
                distance=12.5,
                bearing=135.0,
                direction="SE",
                strikes=2,
                peak_current=-8.0,
                cloud_cover=40.0,
                ellipse_major=1.2,
            ),
            FMILightningStruct(
                time=strike_time,
                distance=18.0,
                bearing=225.0,
                direction="SW",
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


def _lightning_payload(
    latitude: float,
    longitude: float,
    timestamp: datetime,
) -> bytes:
    """Build one aligned synthetic FMI lightning group for HA lifecycle tests."""
    return (
        "<root>"
        f"<positions>{latitude} {longitude} {timestamp.timestamp()}</positions>"
        "<doubleOrNilReasonTupleList>1 12.5 40.0 1.2</doubleOrNilReasonTupleList>"
        "</root>"
    ).encode()


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
    assert current.attributes["apparent_temperature"] == -7.0
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
    assert hourly[0]["apparent_temperature"] == -7.0
    assert hourly[0]["precipitation_probability"] == 25
    assert daily[0]["templow"] == -5.0
    assert daily[0]["apparent_temperature"] == -7.0
    assert "precipitation_probability" not in daily[0]

    temperature = hass.states.get("sensor.helsinki_temperature")
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    sea_level = hass.states.get("sensor.helsinki_sea_level")
    assert temperature is not None and temperature.state == "-4.0"
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert lightning is not None and lightning.state == "12.5 km · SE"
    assert lightning.attributes["distance"] == 12.5
    assert lightning.attributes["bearing"] == 135.0
    assert lightning.attributes["direction"] == "SE"
    assert lightning.attributes["attribution"] == "Weather Data provided by FMI"
    assert "location" not in lightning.attributes
    assert len(lightning.attributes["OBSERVATIONS"]) == 1
    assert lightning.attributes["OBSERVATIONS"][0]["direction"] == "SW"
    assert "location" not in lightning.attributes["OBSERVATIONS"][0]
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


async def test_metric_sensors_and_weather_follow_ha_unit_conversion(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Convert native FMI temperature and pressure through public HA surfaces."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    feels_like = hass.states.get("sensor.helsinki_feels_like")
    pressure = hass.states.get("sensor.helsinki_atmospheric_pressure")
    weather_state = hass.states.get("weather.helsinki")
    assert feels_like is not None and float(feels_like.state) == pytest.approx(19.4)
    assert feels_like.attributes["unit_of_measurement"] == "°F"
    assert pressure is not None and float(pressure.state) == pytest.approx(29.884, abs=0.001)
    assert pressure.attributes["unit_of_measurement"] == "inHg"
    assert weather_state is not None
    assert weather_state.attributes["apparent_temperature"] == 19

    hourly = await _forecast_service(hass, weather_state.entity_id, "hourly")
    daily = await _forecast_service(hass, weather_state.entity_id, "daily")
    assert hourly[0]["apparent_temperature"] == 19
    assert hourly[0]["precipitation_probability"] == 25
    assert daily[0]["apparent_temperature"] == 19
    assert "precipitation_probability" not in daily[0]


async def test_partial_metric_failure_preserves_independent_sources_and_recovers(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep weather siblings, station, lightning, and sea level across partial data loss."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    observation = weather_from_fixture("observation.json", "observation")
    assert weather is not None and observation is not None
    mocks = _patch_sources(
        monkeypatch,
        weather=weather,
        forecast=forecast,
        observation=observation,
    )
    _patch_optional_success(monkeypatch)
    valid_current = cast(fmi_client.CurrentWeatherResult, mocks["weather"].return_value)
    valid_forecast = cast(fmi_client.ForecastResult, mocks["forecast"].return_value)
    partial_weather = weather._replace(
        data=weather.data._replace(feels_like=models.Value(None, "°C"))
    )
    partial_current = fmi_client.CurrentWeatherResult(
        partial_weather,
        fmi_client.ForecastProbabilities(None, None),
    )
    partial_forecast = fmi_client.ForecastResult(forecast, MappingProxyType({}))
    mocks["weather"].side_effect = [valid_current, partial_current, valid_current]
    mocks["forecast"].side_effect = [valid_forecast, partial_forecast, valid_forecast]
    entry = _entry(
        hass,
        options={CONF_LIGHTNING: True, CONF_OBSERVATION_STATION: 101004},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    feels_like = hass.states.get("sensor.helsinki_feels_like")
    probability = hass.states.get("sensor.helsinki_precipitation_probability")
    assert feels_like is not None and feels_like.state != STATE_UNAVAILABLE
    assert probability is not None and probability.state != STATE_UNAVAILABLE

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    main = hass.states.get("weather.helsinki")
    station = hass.states.get("weather.helsinki_kaisaniemi_observation")
    feels_like = hass.states.get("sensor.helsinki_feels_like")
    probability = hass.states.get("sensor.helsinki_precipitation_probability")
    dew_point = hass.states.get("sensor.helsinki_dew_point")
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    sea_level = hass.states.get("sensor.helsinki_sea_level")
    assert main is not None and main.state != STATE_UNAVAILABLE
    assert station is not None and station.state != STATE_UNAVAILABLE
    assert feels_like is not None and feels_like.state == STATE_UNAVAILABLE
    assert probability is not None and probability.state == STATE_UNAVAILABLE
    assert dew_point is not None and dew_point.state != STATE_UNAVAILABLE
    assert lightning is not None and lightning.state != STATE_UNAVAILABLE
    assert sea_level is not None and sea_level.state != STATE_UNAVAILABLE

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    feels_like = hass.states.get("sensor.helsinki_feels_like")
    probability = hass.states.get("sensor.helsinki_precipitation_probability")
    assert feels_like is not None and feels_like.state != STATE_UNAVAILABLE
    assert probability is not None and probability.state != STATE_UNAVAILABLE


async def test_entity_state_and_metric_name_translations_load_from_integration(
    hass: HomeAssistant,
) -> None:
    """Expose the finite empty token in both shipped frontend languages."""
    key = "component.fmi.entity.sensor.lightning_strikes.state.no_strikes"

    english = await translation.async_get_translations(hass, "en", "entity", {DOMAIN})
    finnish = await translation.async_get_translations(hass, "fi", "entity", {DOMAIN})

    assert english[key] == "No lightning strikes"
    assert finnish[key] == "Ei salamaniskuja"
    best_time_key = "component.fmi.entity.sensor.best_time_of_day.state.no_suitable_time"
    assert english[best_time_key] == "No suitable time today"
    assert finnish[best_time_key] == "Ei sopivaa aikaa tänään"

    sensor_names = {
        "feels_like": ("Feels like", "Tuntuu kuin"),
        "dew_point": ("Dew point", "Kastepiste"),
        "atmospheric_pressure": ("Atmospheric pressure", "Ilmanpaine"),
        "low_cloud_cover": ("Low cloud cover", "Alapilvisyys"),
        "medium_cloud_cover": ("Medium cloud cover", "Keskipilvisyys"),
        "high_cloud_cover": ("High cloud cover", "Yläpilvisyys"),
        "precipitation_probability": (
            "Precipitation probability",
            "Sateen todennäköisyys",
        ),
        "thunderstorm_probability": (
            "Thunderstorm probability",
            "Ukkosen todennäköisyys",
        ),
    }
    for sensor_key, (english_name, finnish_name) in sensor_names.items():
        name_key = f"component.fmi.entity.sensor.{sensor_key}.name"
        assert english[name_key] == english_name
        assert finnish[name_key] == finnish_name


async def test_lightning_empty_failure_and_recovery_transitions(
    hass: HomeAssistant,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Replace every lightning state and attribute across source transitions."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    strike_time = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    first = FMILightningStruct(
        time=strike_time,
        distance=12.5,
        bearing=135.0,
        direction="SE",
        strikes=2,
        peak_current=-8.0,
        cloud_cover=40.0,
        ellipse_major=1.2,
    )
    second = FMILightningStruct(
        time=strike_time.replace(minute=30),
        distance=18.0,
        bearing=225.0,
        direction="SW",
        strikes=1,
        peak_current=-4.0,
        cloud_cover=30.0,
        ellipse_major=0.8,
    )
    outcomes: list[list[FMILightningStruct] | Exception] = [
        [],
        [first],
        [],
        OptionalSourceError("synthetic outage"),
        OptionalSourceError("synthetic outage"),
        [],
        [second],
    ]

    async def update_lightning(self: FMIDataUpdateCoordinator) -> None:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        self.lightning_data = outcome

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_lightning_strikes",
        update_lightning,
    )
    entry = _entry(hass, options={CONF_LIGHTNING: True})
    caplog.set_level("INFO", logger="custom_components.fmi.coordinator")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator

    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    assert lightning is not None
    assert lightning.state == "no_strikes"
    assert coordinator.source_availability["lightning"] is True
    assert "distance" not in lightning.attributes
    assert "OBSERVATIONS" not in lightning.attributes

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    assert lightning is not None
    assert lightning.state == "12.5 km · SE"
    assert lightning.attributes["distance"] == 12.5
    assert lightning.attributes["bearing"] == 135.0
    assert lightning.attributes["direction"] == "SE"

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    assert lightning is not None
    assert lightning.state == "no_strikes"
    assert "distance" not in lightning.attributes
    assert "OBSERVATIONS" not in lightning.attributes

    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        lightning = hass.states.get("sensor.helsinki_lightning_strikes")
        assert lightning is not None
        assert lightning.state == STATE_UNAVAILABLE
        assert "distance" not in lightning.attributes
        assert "OBSERVATIONS" not in lightning.attributes

    assert caplog.messages.count("FMI: lightning source unavailable: synthetic outage") == 1

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    assert lightning is not None
    assert lightning.state == "no_strikes"
    assert caplog.messages.count("FMI: lightning source recovered") == 1

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    lightning = hass.states.get("sensor.helsinki_lightning_strikes")
    assert lightning is not None
    assert lightning.state == "18.0 km · SW"
    assert lightning.attributes["distance"] == 18.0
    assert lightning.attributes["bearing"] == 225.0
    assert lightning.attributes["direction"] == "SW"
    assert lightning.attributes["strikes"] == 1


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
    old_coordinator = entry.runtime_data.coordinator
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
    lightning_entry = registry.async_get("sensor.helsinki_lightning_strikes")
    assert lightning_entry is not None
    lightning_entry = registry.async_update_entity(
        lightning_entry.entity_id,
        new_entity_id="sensor.custom_lightning_watch",
    )
    lightning_identity = (
        lightning_entry.id,
        lightning_entry.unique_id,
        lightning_entry.config_entry_id,
        lightning_entry.device_id,
        lightning_entry.disabled_by,
    )
    assert hass.states.get("sensor.custom_lightning_watch") is not None
    enabled_coordinator = entry.runtime_data.coordinator

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
        "sensor.custom_lightning_watch",
        "weather.helsinki_daily",
        "weather.helsinki_kaisaniemi_observation",
    ):
        state = hass.states.get(entity_id)
        assert state is not None and state.state == STATE_UNAVAILABLE
    main_after_disable = registry.async_get("weather.helsinki")
    assert main_after_disable is not None
    assert main_after_disable.id == main_registry_entry.id
    disabled_lightning = registry.async_get("sensor.custom_lightning_watch")
    assert disabled_lightning is not None
    assert (
        disabled_lightning.id,
        disabled_lightning.unique_id,
        disabled_lightning.config_entry_id,
        disabled_lightning.device_id,
        disabled_lightning.disabled_by,
    ) == lightning_identity

    await _configure_options(hass, entry, **{CONF_LIGHTNING: True})

    restored_lightning = registry.async_get("sensor.custom_lightning_watch")
    assert restored_lightning is not None
    assert (
        restored_lightning.id,
        restored_lightning.unique_id,
        restored_lightning.config_entry_id,
        restored_lightning.device_id,
        restored_lightning.disabled_by,
    ) == lightning_identity
    restored_state = hass.states.get("sensor.custom_lightning_watch")
    assert restored_state is not None and restored_state.state == "12.5 km · SE"


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
    old_coordinator = entry.runtime_data.coordinator
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
    reloaded_coordinator = entry.runtime_data.coordinator

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
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
    assert DOMAIN not in hass.data
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
    coordinator = entry.runtime_data.coordinator
    original_unload = hass.config_entries.async_unload_platforms
    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    )

    assert not await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert entry.runtime_data.coordinator is coordinator
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
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None

    await observation_coordinator.async_refresh()
    await hass.async_block_till_done()

    observation_state = hass.states.get("weather.fmi_observation")
    assert observation_state is not None
    assert observation_state.state == "partlycloudy"
    assert observation_state.attributes["temperature"] == 6.5
    assert observation_state.attributes["apparent_temperature"] == 3.1


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
    tampere_coordinator = tampere_entry.runtime_data.coordinator

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


async def test_two_loaded_entries_calculate_one_strike_from_their_own_coordinates(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Run one FMI group through each loaded entry's parser and public sensor."""
    helsinki = weather_from_fixture("forecast_normal.json")
    helsinki_forecast = forecast_from_fixture("forecast_normal.json")
    assert helsinki is not None
    tampere = helsinki._replace(place="Tampere", lat=61.5, lon=23.76)
    tampere_forecast = helsinki_forecast._replace(place="Tampere", lat=61.5, lon=23.76)
    weather_by_location = {(60.17, 24.94): helsinki, (61.5, 23.76): tampere}
    forecast_by_location = {
        (60.17, 24.94): helsinki_forecast,
        (61.5, 23.76): tampere_forecast,
    }
    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        AsyncMock(side_effect=lambda lat, lon: weather_by_location[(lat, lon)]),
    )
    monkeypatch.setattr(
        fmi_client,
        "async_forecast_by_coordinates",
        AsyncMock(side_effect=lambda lat, lon, *_: forecast_by_location[(lat, lon)]),
    )
    monkeypatch.setattr(fmi_client, "async_observation_by_place", AsyncMock(return_value=None))
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    payload = _lightning_payload(60.20, 24.90, now)

    async def parse_same_strike(self: FMIDataUpdateCoordinator) -> None:
        coordinator = cast(Any, self)
        self.lightning_data = coordinator._FMIDataUpdateCoordinator__parse_lightning_payload(
            payload,
            now,
        )

    async def empty_sea_level(self: FMIDataUpdateCoordinator) -> None:
        self.mareo_data = None

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_lightning_strikes",
        parse_same_strike,
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        empty_sea_level,
    )
    helsinki_entry = _entry(
        hass,
        entry_id="lightning-helsinki",
        options={CONF_LIGHTNING: True},
    )
    tampere_entry = _entry(
        hass,
        title="Synthetic Tampere",
        latitude=61.5,
        longitude=23.76,
        entry_id="lightning-tampere",
        options={CONF_LIGHTNING: True},
    )

    for entry in (helsinki_entry, tampere_entry):
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    helsinki_state = hass.states.get("sensor.helsinki_lightning_strikes")
    tampere_state = hass.states.get("sensor.tampere_lightning_strikes")
    assert helsinki_state is not None and tampere_state is not None
    assert helsinki_state.state == "4.0 km · NW"
    assert helsinki_state.attributes["direction"] == "NW"
    assert helsinki_state.attributes["distance"] == 4.01
    assert tampere_state.state == "157.6 km · SE"
    assert tampere_state.attributes["direction"] == "SE"
    assert 150 < tampere_state.attributes["distance"] < 170
    assert tampere_state.attributes["distance"] != helsinki_state.attributes["distance"]
    assert helsinki_state.attributes["OBSERVATIONS"] == []
    assert tampere_state.attributes["OBSERVATIONS"] == []
    assert helsinki_entry.runtime_data.coordinator.latitude == 60.17
    assert tampere_entry.runtime_data.coordinator.latitude == 61.5


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
    coordinator = entry.runtime_data.coordinator

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

    coordinator = entry.runtime_data.coordinator
    assert coordinator.best_condition.status == BEST_CONDITION_NO_SUITABLE
    state = hass.states.get("sensor.helsinki_best_time_of_day")
    assert state is not None and state.state == BEST_CONDITION_NO_SUITABLE
    for attribute in (
        "location",
        "time",
        "temperature",
        "relative_humidity",
        "precipitation",
        "wind_speed",
        "apparent_temperature",
        "precipitation_probability",
        "thunderstorm_probability",
    ):
        assert attribute not in state.attributes


async def test_best_time_selected_state_preserves_and_extends_attributes(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Expose the compatible HH:MM state and all transparent selection factors."""
    weather = weather_from_fixture("forecast_normal.json")
    source_forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    current_time = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
    selected = source_forecast.forecasts[0]._replace(
        time=current_time.replace(hour=13),
        temperature=models.Value(18.0, "°C"),
        feels_like=models.Value(20.0, "°C"),
        humidity=models.Value(50.0, "%"),
        wind_speed=models.Value(4.0, "m/s"),
        precipitation_amount=models.Value(0.1, "mm/h"),
        symbol=models.Value(1.0, ""),
    )
    forecast = source_forecast._replace(forecasts=[selected])
    mocks = _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    monkeypatch.setattr("custom_components.fmi.dt_util.now", lambda: current_time)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    state = hass.states.get("sensor.helsinki_best_time_of_day")
    assert coordinator.best_condition.time is not None
    expected_state = coordinator.best_condition.time.strftime("%H:%M")
    assert state is not None and state.state == expected_state
    assert state.attributes["location"] == "Helsinki"
    assert state.attributes["temperature"] == 18.0
    assert state.attributes["apparent_temperature"] == 20.0
    assert state.attributes["relative_humidity"] == 50.0
    assert state.attributes["wind_speed"] == 4.0
    assert state.attributes["precipitation"] == 0.1
    assert state.attributes["precipitation_probability"] == 25.0
    assert state.attributes["thunderstorm_probability"] == 5.0
    assert state.attributes["time"] == selected.time
    assert isinstance(state.attributes["time"], datetime)
    assert state.attributes["time"].utcoffset() is not None
    for private_or_internal_attribute in (
        "latitude",
        "longitude",
        "entity_identity",
        "rank",
        "score",
        "raw_forecast",
    ):
        assert private_or_internal_attribute not in state.attributes

    complete_forecast = cast(fmi_client.ForecastResult, mocks["forecast"].return_value)
    incomplete_forecast = fmi_client.ForecastResult(forecast, MappingProxyType({}))
    mocks["forecast"].side_effect = [incomplete_forecast, complete_forecast]

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.helsinki_best_time_of_day")
    assert coordinator.best_condition.status == BEST_CONDITION_NOT_AVAIL
    assert state is not None and state.state == STATE_UNAVAILABLE
    assert "time" not in state.attributes

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.helsinki_best_time_of_day")
    assert state is not None and state.state == expected_state


async def test_best_time_options_reload_reselects_without_replacing_entity(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Apply feels-like limits after reload while retaining registry identity."""
    weather = weather_from_fixture("forecast_normal.json")
    source_forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    current_time = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
    first = source_forecast.forecasts[0]._replace(
        time=current_time.replace(hour=13),
        temperature=models.Value(18.0, "°C"),
        feels_like=models.Value(18.0, "°C"),
        humidity=models.Value(50.0, "%"),
        wind_speed=models.Value(4.0, "m/s"),
        precipitation_amount=models.Value(0.1, "mm/h"),
    )
    second = source_forecast.forecasts[1]._replace(
        time=current_time.replace(hour=14),
        temperature=models.Value(25.0, "°C"),
        feels_like=models.Value(25.0, "°C"),
        humidity=models.Value(50.0, "%"),
        wind_speed=models.Value(4.0, "m/s"),
        precipitation_amount=models.Value(0.1, "mm/h"),
    )
    forecast = source_forecast._replace(forecasts=[first, second])
    _patch_sources(monkeypatch, weather=weather, forecast=forecast)
    monkeypatch.setattr("custom_components.fmi.dt_util.now", lambda: current_time)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    before = registry.async_get("sensor.helsinki_best_time_of_day")
    assert before is not None
    before_state = hass.states.get(before.entity_id)
    assert before_state is not None
    before_time = entry.runtime_data.coordinator.best_condition.time
    assert before_time is not None
    assert before_state.state == before_time.strftime("%H:%M")
    assert entry.runtime_data.coordinator.best_condition.temperature == 18.0

    await _configure_options(
        hass,
        entry,
        **{CONF_MIN_TEMP: 24, CONF_MAX_TEMP: 30},
    )

    after = registry.async_get("sensor.helsinki_best_time_of_day")
    assert after is not None
    assert after.id == before.id
    assert after.unique_id == before.unique_id
    after_state = hass.states.get(after.entity_id)
    assert after_state is not None
    after_time = entry.runtime_data.coordinator.best_condition.time
    assert after_time is not None
    assert after_state.state == after_time.strftime("%H:%M")
    assert entry.runtime_data.coordinator.best_condition.temperature == 25.0


async def test_two_entries_select_best_time_from_their_own_forecasts_and_options(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep Best-time data and preferences isolated between simultaneous entries."""
    weather = weather_from_fixture("forecast_normal.json")
    source_forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    current_time = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
    helsinki_sample = source_forecast.forecasts[0]._replace(
        time=current_time.replace(hour=13),
        temperature=models.Value(18.0, "°C"),
        feels_like=models.Value(18.0, "°C"),
        humidity=models.Value(50.0, "%"),
        wind_speed=models.Value(4.0, "m/s"),
        precipitation_amount=models.Value(0.1, "mm/h"),
    )
    tampere_sample = source_forecast.forecasts[1]._replace(
        time=current_time.replace(hour=14),
        temperature=models.Value(25.0, "°C"),
        feels_like=models.Value(25.0, "°C"),
        humidity=models.Value(50.0, "%"),
        wind_speed=models.Value(4.0, "m/s"),
        precipitation_amount=models.Value(0.1, "mm/h"),
    )
    locations = {
        (60.17, 24.94): (
            weather,
            source_forecast._replace(forecasts=[helsinki_sample]),
        ),
        (61.5, 23.76): (
            weather._replace(place="Tampere", lat=61.5, lon=23.76),
            source_forecast._replace(
                place="Tampere",
                lat=61.5,
                lon=23.76,
                forecasts=[tampere_sample],
            ),
        ),
    }

    async def current(latitude: float, longitude: float):
        location_weather = locations[(latitude, longitude)][0]
        return fmi_client.CurrentWeatherResult(
            location_weather,
            fmi_client.ForecastProbabilities(20.0, 0.0),
        )

    async def forecasts(latitude: float, longitude: float, *_):
        location_forecast = locations[(latitude, longitude)][1]
        return fmi_client.ForecastResult(
            location_forecast,
            MappingProxyType(
                {
                    sample.time: fmi_client.ForecastProbabilities(20.0, 0.0)
                    for sample in location_forecast.forecasts
                }
            ),
        )

    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", current)
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", forecasts)
    monkeypatch.setattr(fmi_client, "async_observation_by_place", AsyncMock(return_value=None))

    async def empty_sea_level(self: FMIDataUpdateCoordinator) -> None:
        self.mareo_data = None

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        empty_sea_level,
    )
    monkeypatch.setattr("custom_components.fmi.dt_util.now", lambda: current_time)
    helsinki_entry = _entry(hass, entry_id="best-helsinki")
    tampere_entry = _entry(
        hass,
        title="Synthetic Tampere",
        latitude=61.5,
        longitude=23.76,
        entry_id="best-tampere",
        options={CONF_MIN_TEMP: 24, CONF_MAX_TEMP: 30},
    )

    for entry in (helsinki_entry, tampere_entry):
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    helsinki_best = helsinki_entry.runtime_data.coordinator.best_condition
    tampere_best = tampere_entry.runtime_data.coordinator.best_condition
    assert helsinki_best.time is not None and tampere_best.time is not None
    assert helsinki_best.temperature == 18.0
    assert tampere_best.temperature == 25.0
    assert helsinki_best.time != tampere_best.time
    helsinki_state = hass.states.get("sensor.helsinki_best_time_of_day")
    tampere_state = hass.states.get("sensor.tampere_best_time_of_day")
    assert helsinki_state is not None and tampere_state is not None
    assert helsinki_state.state != tampere_state.state
