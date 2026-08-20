# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Opt-in probes against public FMI data and Home Assistant exposure."""

from __future__ import annotations

import asyncio
import math
import os
import socket
from collections import Counter
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_socket
from fmi_weather_client.errors import ClientError, ServerError
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    STATE_UNAVAILABLE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import RequestException

from custom_components.fmi import FMIDataUpdateCoordinator
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import (
    CONF_ENTITY_IDENTITY,
    CONF_FORECAST_DAYS,
    CONF_OBSERVATION_STATION,
    DOMAIN,
)
from tests.helpers.live_budget import LiveRequestBudget
from tests.helpers.live_fmi import (
    LiveContractError,
    validate_daily_precipitation,
    validate_first_available_local_day_ha_metrics,
    validate_first_available_local_day_probability_supplements,
    validate_ha_forecast,
    validate_model_forecast,
    validate_model_weather,
    validate_probabilities,
)

pytestmark = pytest.mark.live

SOUTHERN_LOCATION = ("Helsinki", 60.17, 24.94)
NORTHERN_LOCATION = ("Kilpisjarvi", 69.05, 20.79)
OBSERVATION_STATION_ID = 101004
_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_GETHOSTBYNAME = socket.gethostbyname
_REAL_GETHOSTBYNAME_EX = socket.gethostbyname_ex
_REAL_SOCKET_CONNECT = socket.socket.connect


def _set_socket_connect(connect: Any) -> None:
    """Set the connect implementation on pytest-socket's mutable socket class."""
    socket_class = cast(Any, socket.socket)
    socket_class.connect = connect


@pytest.fixture(autouse=True)
def enable_live_network() -> Generator[None]:
    """Undo the HA test plugin's per-test network guard only for live tests."""
    guarded_getaddrinfo = socket.getaddrinfo
    guarded_gethostbyname = socket.gethostbyname
    guarded_gethostbyname_ex = socket.gethostbyname_ex
    guarded_connect = socket.socket.connect
    pytest_socket.enable_socket()
    _set_socket_connect(_REAL_SOCKET_CONNECT)
    socket.getaddrinfo = _REAL_GETADDRINFO
    socket.gethostbyname = _REAL_GETHOSTBYNAME
    socket.gethostbyname_ex = _REAL_GETHOSTBYNAME_EX
    yield
    socket.getaddrinfo = guarded_getaddrinfo
    socket.gethostbyname = guarded_gethostbyname
    socket.gethostbyname_ex = guarded_gethostbyname_ex
    _set_socket_connect(guarded_connect)
    pytest_socket.disable_socket(allow_unix_socket=True)


async def _live_call[T](label: str, operation: Callable[[], Awaitable[T]]) -> T:
    """Retry one bounded transport/service failure and classify final output."""
    for attempt in range(2):
        try:
            budget = LiveRequestBudget(
                Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
            )
            async with budget.request(), asyncio.timeout(15):
                return await operation()
        except ClientError as error:
            pytest.fail(
                f"FMI request/contract failure for {label}: "
                f"HTTP {getattr(error, 'status_code', 'unknown')} "
                f"{getattr(error, 'message', '')}",
                pytrace=False,
            )
        except (TimeoutError, OSError, RequestException, ServerError) as error:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            pytest.fail(
                f"FMI transport/service failure for {label} after 2 attempts: "
                f"{type(error).__name__}: {error}",
                pytrace=False,
            )
        except (
            AttributeError,
            KeyError,
            SyntaxError,
            TypeError,
            ValueError,
        ) as error:
            pytest.fail(
                f"FMI parsing/contract failure for {label}: {type(error).__name__}: {error}",
                pytrace=False,
            )
    raise AssertionError("unreachable live retry state")


async def test_dependency_place_resolution_contract() -> None:
    """Resolve a public name and validate its point through the production boundary."""
    resolution = await _live_call(
        "Helsinki place resolution",
        lambda: fmi_client.async_resolve_place(SOUTHERN_LOCATION[0]),
    )
    if resolution is None:
        raise LiveContractError("Helsinki place resolution returned no forecast point")
    if not 55 <= resolution.latitude <= 75 or not 5 <= resolution.longitude <= 35:
        raise LiveContractError("Helsinki place resolution returned a point outside the region")
    current_result = await _live_call(
        "resolved Helsinki coordinate validation",
        lambda: fmi_client.async_weather_by_coordinates(
            resolution.latitude,
            resolution.longitude,
        ),
    )
    if current_result is None:
        raise LiveContractError("resolved Helsinki coordinate validation returned no data")
    validate_model_weather(
        current_result.weather,
        "resolved Helsinki coordinate validation",
        max_age=timedelta(hours=2),
    )
    validate_probabilities(
        current_result.probabilities,
        "resolved Helsinki coordinate validation",
    )


async def test_dependency_northern_forecast_contract() -> None:
    """Detect installed-client or WFS drift at a northern public point."""
    label, latitude, longitude = NORTHERN_LOCATION
    forecast_result = await _live_call(
        f"{label} forecast",
        lambda: fmi_client.async_forecast_by_coordinates(latitude, longitude, 1, 48),
    )
    samples = validate_model_forecast(forecast_result.forecast, f"{label} forecast")
    validate_first_available_local_day_probability_supplements(
        samples,
        forecast_result.probabilities_by_time,
        f"{label} forecast",
    )


async def test_dependency_observation_contract() -> None:
    """Detect station-query drift and reject implausibly stale observations."""
    observation = await _live_call(
        "Helsinki Kumpula observation",
        lambda: fmi_client.async_observation_by_station_id(OBSERVATION_STATION_ID),
    )
    validate_model_weather(
        observation,
        "Helsinki Kumpula observation",
        max_age=timedelta(minutes=45),
    )


async def _forecast_service(
    hass: HomeAssistant,
    entity_id: str,
    forecast_type: str,
) -> list[dict[str, Any]]:
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": entity_id, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    if not isinstance(response, dict):
        raise LiveContractError(f"Home Assistant {forecast_type} service returned no mapping")
    entity_response = response.get(entity_id)
    if not isinstance(entity_response, dict) or not isinstance(
        entity_response.get("forecast"), list
    ):
        raise LiveContractError(
            f"Home Assistant {forecast_type} service omitted {entity_id} forecast"
        )
    return cast(list[dict[str, Any]], entity_response["forecast"])


def _finite_attribute(
    attributes: dict[str, Any], name: str, minimum: float, maximum: float
) -> float:
    raw = attributes.get(name)
    if not isinstance(raw, int | float | str):
        raise LiveContractError(f"Home Assistant attribute {name} is not numeric: {raw!r}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise LiveContractError(
            f"Home Assistant attribute {name} is not numeric: {raw!r}"
        ) from error
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise LiveContractError(f"Home Assistant attribute {name}={raw!r} is implausible")
    return value


async def test_home_assistant_live_entity_and_forecast_contract(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Prove public FMI values reach dashboard-facing Home Assistant APIs."""
    await hass.config.async_set_time_zone("Europe/Helsinki")
    request_counts: Counter[str] = Counter()
    original_weather = fmi_client.async_weather_by_coordinates
    original_forecast = fmi_client.async_forecast_by_coordinates
    original_place = fmi_client.async_observation_by_place
    original_station = fmi_client.async_observation_by_station_id

    async def traced_weather(latitude: float, longitude: float):
        request_counts["current"] += 1
        async with LiveRequestBudget(
            Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
        ).request():
            return await original_weather(latitude, longitude)

    async def traced_forecast(
        latitude: float,
        longitude: float,
        timestep_hours: int,
        forecast_points: int,
    ):
        request_counts["forecast"] += 1
        async with LiveRequestBudget(
            Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
        ).request():
            return await original_forecast(
                latitude,
                longitude,
                timestep_hours,
                forecast_points,
            )

    async def traced_place(place: str):
        request_counts["place_fallback"] += 1
        async with LiveRequestBudget(
            Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
        ).request():
            return await original_place(place)

    async def traced_station(station_id: int):
        request_counts["station"] += 1
        async with LiveRequestBudget(
            Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
        ).request():
            return await original_station(station_id)

    async def skip_unrelated_sea_level(self: FMIDataUpdateCoordinator) -> None:
        self.mareo_data = None

    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", traced_weather)
    monkeypatch.setattr(fmi_client, "async_forecast_by_coordinates", traced_forecast)
    monkeypatch.setattr(fmi_client, "async_observation_by_place", traced_place)
    monkeypatch.setattr(fmi_client, "async_observation_by_station_id", traced_station)
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        skip_unrelated_sea_level,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Public Helsinki",
        unique_id="fmi:live-public-helsinki",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: SOUTHERN_LOCATION[1],
            CONF_LONGITUDE: SOUTHERN_LOCATION[2],
            CONF_ENTITY_IDENTITY: "live:public-helsinki",
        },
        options={
            CONF_FORECAST_DAYS: 2,
            CONF_OBSERVATION_STATION: OBSERVATION_STATION_ID,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    except Exception as error:  # pylint: disable=broad-exception-caught
        pytest.fail(
            f"Home Assistant setup/exposure failure after live FMI calls: "
            f"{type(error).__name__}: {error}",
            pytrace=False,
        )

    assert entry.state is ConfigEntryState.LOADED
    assert request_counts["current"] == 1
    assert request_counts["forecast"] == 1
    assert request_counts["station"] == 1
    assert sum(request_counts.values()) <= 4

    weather_states = hass.states.async_all(WEATHER_DOMAIN)
    main = next(
        (state for state in weather_states if state.attributes.get("supported_features", 0)),
        None,
    )
    observation_state = next(
        (state for state in weather_states if not state.attributes.get("supported_features", 0)),
        None,
    )
    if main is None or observation_state is None:
        raise LiveContractError("Home Assistant omitted main or observation weather entity")
    assert main.state != STATE_UNAVAILABLE
    assert observation_state.state != STATE_UNAVAILABLE
    assert main.attributes.get("temperature_unit") == UnitOfTemperature.CELSIUS
    assert main.attributes.get("pressure_unit") == UnitOfPressure.HPA
    assert main.attributes.get("wind_speed_unit") == UnitOfSpeed.KILOMETERS_PER_HOUR
    assert main.attributes.get("precipitation_unit") == UnitOfPrecipitationDepth.MILLIMETERS
    assert observation_state.attributes.get("temperature_unit") == UnitOfTemperature.CELSIUS
    assert observation_state.attributes.get("pressure_unit") == UnitOfPressure.HPA
    current_temperature = _finite_attribute(main.attributes, "temperature", -90.0, 60.0)
    current_apparent_temperature = _finite_attribute(
        main.attributes,
        "apparent_temperature",
        -120.0,
        80.0,
    )
    observation_temperature = _finite_attribute(
        observation_state.attributes,
        "temperature",
        -90.0,
        60.0,
    )

    coordinator = entry.runtime_data.coordinator
    observation_coordinator = entry.runtime_data.observation_coordinator
    assert observation_coordinator is not None
    current_sample = validate_model_weather(
        coordinator.get_weather(),
        "Home Assistant current source",
        max_age=timedelta(hours=2),
    )
    raw_observation = validate_model_weather(
        observation_coordinator.get_observation(),
        "Home Assistant station source",
        max_age=timedelta(minutes=45),
    )
    assert current_temperature == pytest.approx(float(current_sample.temperature.value), abs=0.1)
    assert current_apparent_temperature == pytest.approx(
        float(current_sample.feels_like.value), abs=0.6
    )
    assert observation_temperature == pytest.approx(
        float(raw_observation.temperature.value), abs=0.1
    )
    forecast_samples = coordinator.get_hourly_forecasts()
    validate_first_available_local_day_probability_supplements(
        forecast_samples,
        {
            sample.time.astimezone(UTC): coordinator.get_forecast_probabilities(sample.time)
            for sample in forecast_samples
        },
        "Home Assistant Helsinki forecast source",
    )

    registry_entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    temperature_state = next(
        (
            state
            for registry_entry in registry_entries
            if registry_entry.domain == "sensor"
            and registry_entry.original_device_class == "temperature"
            if (state := hass.states.get(registry_entry.entity_id)) is not None
        ),
        None,
    )
    if temperature_state is None:
        raise LiveContractError("Home Assistant omitted the temperature sensor")
    assert temperature_state.state != STATE_UNAVAILABLE
    assert temperature_state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    try:
        sensor_temperature = float(temperature_state.state)
    except ValueError as error:
        raise LiveContractError("Home Assistant temperature sensor state is not numeric") from error
    if not math.isfinite(sensor_temperature) or not -90.0 <= sensor_temperature <= 60.0:
        raise LiveContractError("Home Assistant temperature sensor state is implausible")

    metric_ranges = {
        "Feels_like": (-120.0, 80.0),
        "Dew_point": (-100.0, 60.0),
        "Atmospheric_pressure": (800.0, 1200.0),
        "Low_cloud_cover": (0.0, 100.0),
        "Medium_cloud_cover": (0.0, 100.0),
        "High_cloud_cover": (0.0, 100.0),
        "Precipitation_probability": (0.0, 100.0),
        "Thunderstorm_probability": (0.0, 100.0),
    }
    by_unique_suffix = {
        suffix: hass.states.get(registry_entry.entity_id)
        for suffix in metric_ranges
        for registry_entry in registry_entries
        if registry_entry.unique_id.endswith(suffix)
    }
    for suffix, (minimum, maximum) in metric_ranges.items():
        state = by_unique_suffix.get(suffix)
        if state is None or state.state == STATE_UNAVAILABLE:
            raise LiveContractError(f"Home Assistant omitted live {suffix} sensor data")
        _finite_attribute({"state": state.state}, "state", minimum, maximum)

    hourly_items = await _forecast_service(hass, main.entity_id, "hourly")
    daily_items = await _forecast_service(hass, main.entity_id, "daily")
    hourly = validate_ha_forecast(hourly_items, "hourly")
    daily = validate_ha_forecast(daily_items, "daily")
    validate_first_available_local_day_ha_metrics(hourly, "hourly")
    validate_daily_precipitation(hourly, daily)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
