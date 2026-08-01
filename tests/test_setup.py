# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Smoke tests for FMI config-entry setup."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.components.weather import (
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
)
from homeassistant.components.weather.const import DATA_COMPONENT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonValueType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import FMIDataUpdateCoordinator
from custom_components.fmi.const import DOMAIN
from custom_components.fmi.weather import FMIWeatherEntity


def _value(value: float, unit: str = "") -> SimpleNamespace:
    return SimpleNamespace(value=value, unit=unit)


def _weather_data() -> SimpleNamespace:
    return SimpleNamespace(
        time=datetime.now(UTC),
        temperature=_value(12.5, "°C"),
        dew_point=_value(7.0, "°C"),
        pressure=_value(1012.0, "hPa"),
        humidity=_value(65.0, "%"),
        wind_direction=_value(180.0, "°"),
        wind_speed=_value(4.0, "m/s"),
        wind_gust=_value(7.0, "m/s"),
        wind_max=_value(6.0, "m/s"),
        symbol=_value(2.0),
        cloud_cover=_value(40.0, "%"),
        precipitation_amount=_value(0.0, "mm"),
    )


async def test_mocked_config_entry_loads(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Load the integration through Home Assistant's config-entry API."""
    data = _weather_data()
    weather = SimpleNamespace(place="Helsinki", data=data)

    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_fetch_forecast_weather",
        AsyncMock(return_value=weather),
    )

    async def mock_fetch_forecast(self) -> None:
        self.forecast = SimpleNamespace(forecasts=[data])

    monkeypatch.setattr(FMIDataUpdateCoordinator, "_fetch_forecast", mock_fetch_forecast)
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Helsinki",
        unique_id="60.1699_24.9384",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 60.1699,
            CONF_LONGITUDE: 24.9384,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("weather.helsinki") is not None

    entity = hass.data[DATA_COMPONENT].get_entity("weather.helsinki")
    assert isinstance(entity, FMIWeatherEntity)
    assert entity.native_precipitation_unit == "mm"

    forecast_updates: list[list[JsonValueType] | None] = []
    unsubscribe = entity.async_subscribe_forecast("daily", forecast_updates.append)
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    unsubscribe()

    assert len(forecast_updates) == 1
    update = forecast_updates[0]
    assert update is not None
    forecast = update[0]
    assert isinstance(forecast, dict)
    assert forecast[ATTR_FORECAST_TEMP] == 12.5
    assert forecast[ATTR_FORECAST_PRECIPITATION] == 0.0
    forecast_time = forecast[ATTR_FORECAST_TIME]
    assert isinstance(forecast_time, str)
    assert forecast_time.endswith("+00:00")
