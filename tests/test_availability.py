# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Availability and recovery tests for independent FMI data sources."""

import logging
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

from fmi_weather_client.errors import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_OFFSET,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import RequestException

from custom_components.fmi import FMIDataUpdateCoordinator
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import (
    CONF_LIGHTNING,
    CONF_OBSERVATION_STATION,
    DOMAIN,
)
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture


def _async_response(value):
    if isinstance(value, AsyncMock):
        return value
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


def _patch_fmi_sources(
    monkeypatch,
    *,
    weather=None,
    forecast=None,
    place_observation=None,
    station_observation=None,
):
    mocks = {
        "weather": _async_response(weather),
        "forecast": _async_response(forecast),
        "place_observation": _async_response(place_observation),
        "station_observation": _async_response(station_observation),
    }
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", mocks["weather"])
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", mocks["forecast"])
    monkeypatch.setattr(fmi_client, "async_observation_by_place", mocks["place_observation"])
    monkeypatch.setattr(
        fmi_client,
        "async_observation_by_station_id",
        mocks["station_observation"],
    )
    return mocks


def _patch_sea_level(monkeypatch, update=None) -> None:
    async def async_update(self) -> None:
        if update is not None:
            update(self)

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        async_update,
    )


def _entry(
    hass: HomeAssistant,
    *,
    station_id: int = 0,
    forecast_interval: int | None = None,
    lightning: bool = False,
) -> MockConfigEntry:
    options = {CONF_OBSERVATION_STATION: station_id} if station_id else {}
    if forecast_interval is not None:
        options[CONF_OFFSET] = forecast_interval
    if lightning:
        options[CONF_LIGHTNING] = True
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic Helsinki",
        unique_id="60.17_24.94",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 60.17,
            CONF_LONGITUDE: 24.94,
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_observation_by_place_loads_when_forecast_wfs_fails(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep current conditions available while forecast WFS is unavailable."""
    observation = weather_from_fixture("observation.json", "observation")
    forecast_error = ClientError(400, "Synthetic forecast WFS failure")
    mocks = _patch_fmi_sources(
        monkeypatch,
        weather=forecast_error,
        forecast=forecast_error,
        place_observation=observation,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.get_weather() is observation
    assert coordinator.get_forecasts() == []
    mocks["place_observation"].assert_awaited_once_with("Synthetic Helsinki")
    assert all(state.state != STATE_UNAVAILABLE for state in hass.states.async_all("weather"))
    assert any(
        state.attributes.get("friendly_name", "").endswith("Temperature")
        and state.state != STATE_UNAVAILABLE
        for state in hass.states.async_all("sensor")
    )


async def test_station_observation_loads_when_all_forecast_sources_fail(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Load a configured station even when both current forecast paths fail."""
    observation = weather_from_fixture("observation.json", "observation")
    source_error = ClientError(400, "Synthetic current source failure")
    _patch_fmi_sources(
        monkeypatch,
        weather=source_error,
        forecast=source_error,
        place_observation=source_error,
        station_observation=observation,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass, station_id=101004)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    forecast_coordinator = entry.runtime_data.coordinator
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None
    assert entry.state is ConfigEntryState.LOADED
    assert not forecast_coordinator.last_update_success
    assert observation_coordinator.last_update_success
    assert observation_coordinator.get_observation() is observation
    weather_states = hass.states.async_all("weather")
    assert sum(state.state == STATE_UNAVAILABLE for state in weather_states) == 1
    assert sum(state.state != STATE_UNAVAILABLE for state in weather_states) == 1


async def test_forecast_loads_when_station_observation_fails(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep forecast-backed entities loaded during a station outage."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    station_error = ClientError(400, "Synthetic station failure")
    _patch_fmi_sources(
        monkeypatch,
        weather=weather,
        forecast=forecast,
        station_observation=station_error,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass, station_id=101004)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.last_update_success
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None
    assert not observation_coordinator.last_update_success
    weather_states = hass.states.async_all("weather")
    assert sum(state.state == STATE_UNAVAILABLE for state in weather_states) == 1
    assert sum(state.state != STATE_UNAVAILABLE for state in weather_states) == 1


async def test_coarse_legacy_interval_preserves_hourly_forecast_source(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Fetch every Precipitation1h sample even with a coarse legacy interval."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    mocks = _patch_fmi_sources(monkeypatch, weather=weather, forecast=forecast)
    _patch_sea_level(monkeypatch)
    entry = _entry(hass, forecast_interval=3)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    mocks["forecast"].assert_awaited_once_with(60.17, 24.94, 1, 96)
    assert len(coordinator.get_hourly_forecasts()) == 49
    assert len(coordinator.get_forecasts()) == 17


async def test_both_current_sources_fail_initial_setup(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Enter retry only when forecast/fallback and configured station all fail."""
    source_error = ClientError(400, "Synthetic total current outage")
    _patch_fmi_sources(
        monkeypatch,
        weather=source_error,
        forecast=source_error,
        place_observation=source_error,
        station_observation=source_error,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass, station_id=101004)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert DOMAIN not in hass.data
    entry.async_cancel_retry_setup()


async def test_empty_current_results_enter_setup_retry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Treat None results as unavailable data, not a successful refresh."""
    _patch_fmi_sources(monkeypatch)
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    entry.async_cancel_retry_setup()


async def test_forecast_clears_stale_data_and_recovers_without_log_spam(
    hass: HomeAssistant,
    monkeypatch,
    caplog,
) -> None:
    """Clear stale forecasts and log only outage/recovery transitions."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    forecast_error = ClientError(400, "Synthetic forecast outage")
    forecast_mock = AsyncMock(side_effect=[forecast, forecast_error, forecast_error, forecast])
    _patch_fmi_sources(monkeypatch, weather=weather, forecast=forecast_mock)
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)
    caplog.set_level(logging.INFO, logger="custom_components.fmi.coordinator")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    assert coordinator.get_forecasts()

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.get_forecasts() == []

    await coordinator.async_refresh()
    assert coordinator.get_forecasts() == []

    await coordinator.async_refresh()
    assert coordinator.get_forecasts()

    messages = [record.getMessage() for record in caplog.records]
    assert sum("forecast source unavailable" in message for message in messages) == 1
    assert sum("forecast source recovered" in message for message in messages) == 1


async def test_current_outage_clears_stale_data_and_recovers(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Make current entities unavailable, then recover on a later refresh."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    source_error = ClientError(400, "Synthetic current outage")
    weather_mock = AsyncMock(side_effect=[weather, source_error, source_error, weather])
    place_mock = AsyncMock(side_effect=source_error)
    _patch_fmi_sources(
        monkeypatch,
        weather=weather_mock,
        forecast=forecast,
        place_observation=place_mock,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert coordinator.get_weather() is None
    assert coordinator.get_forecasts() == []
    assert all(state.state == STATE_UNAVAILABLE for state in hass.states.async_all("weather"))

    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.get_weather() is weather
    assert coordinator.get_forecasts()
    assert all(state.state != STATE_UNAVAILABLE for state in hass.states.async_all("weather"))


async def test_transport_error_uses_place_fallback_and_clears_stale_current(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep request-library failures inside the normal source availability policy."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    fallback = weather_from_fixture("observation.json", "observation")
    assert weather is not None and fallback is not None
    transport_error = RequestException("Synthetic connection reset")
    weather_mock = AsyncMock(side_effect=[weather, transport_error, transport_error])
    place_mock = AsyncMock(side_effect=[fallback, transport_error])
    _patch_fmi_sources(
        monkeypatch,
        weather=weather_mock,
        forecast=forecast,
        place_observation=place_mock,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.get_weather() is fallback

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert coordinator.get_weather() is None
    assert coordinator.get_forecasts() == []


async def test_malformed_forecast_keeps_current_weather_available(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Treat a forecast parser failure as forecast-only unavailability."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    _patch_fmi_sources(
        monkeypatch,
        weather=weather,
        forecast=ET.ParseError("Synthetic malformed forecast XML"),
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    assert coordinator.last_update_success
    assert coordinator.get_weather() is weather
    assert coordinator.get_forecasts() == []
    assert all(state.state != STATE_UNAVAILABLE for state in hass.states.async_all("weather"))


async def test_primary_timeout_clears_stale_data_and_recovers(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Clear current data on a core timeout and recover on the next refresh."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    weather_mock = AsyncMock(side_effect=[weather, TimeoutError, weather])
    _patch_fmi_sources(monkeypatch, weather=weather_mock, forecast=forecast)
    _patch_sea_level(monkeypatch)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert coordinator.get_weather() is None
    assert coordinator.get_forecasts() == []
    assert all(state.state == STATE_UNAVAILABLE for state in hass.states.async_all("weather"))

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.get_weather() is weather
    assert coordinator.get_forecasts()
    assert all(state.state != STATE_UNAVAILABLE for state in hass.states.async_all("weather"))


async def test_optional_source_failure_does_not_disable_current_weather(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep optional sea-level parsing outside core availability."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    _patch_fmi_sources(monkeypatch, weather=weather, forecast=forecast)

    def fail_sea_level(self) -> None:
        raise ET.ParseError("Synthetic malformed sea-level payload")

    _patch_sea_level(monkeypatch, fail_sea_level)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success
    assert coordinator.get_weather() is weather
    assert coordinator.mareo_data is None


async def test_lightning_failure_does_not_disable_current_weather(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep an enabled lightning transport failure outside core availability."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    _patch_fmi_sources(monkeypatch, weather=weather, forecast=forecast)
    _patch_sea_level(monkeypatch)

    async def fail_lightning(self) -> None:
        raise TimeoutError("Synthetic lightning timeout")

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_lightning_strikes",
        fail_lightning,
    )
    entry = _entry(hass, lightning=True)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success
    assert coordinator.get_weather() is weather
    assert coordinator.lightning_data is None


async def test_partial_outage_unload_reload_cleans_coordinator_listeners(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Remove one listener per entity and reload during a forecast outage."""
    observation = weather_from_fixture("observation.json", "observation")
    source_error = ClientError(400, "Synthetic forecast outage")
    _patch_fmi_sources(
        monkeypatch,
        weather=source_error,
        forecast=source_error,
        place_observation=source_error,
        station_observation=observation,
    )
    _patch_sea_level(monkeypatch)
    entry = _entry(hass, station_id=101004)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None
    coordinators = [entry.runtime_data.coordinator, observation_coordinator]

    for coordinator in coordinators:
        callbacks = [callback for callback, _ in coordinator._listeners.values()]
        assert callbacks
        assert {callback.__name__ for callback in callbacks} == {"_handle_coordinator_update"}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
    assert all(not coordinator._listeners for coordinator in coordinators)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None
    assert observation_coordinator.last_update_success
