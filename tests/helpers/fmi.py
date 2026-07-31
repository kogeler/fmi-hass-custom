# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Deterministic builders for the installed FMI client contract."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fmi_weather_client import models

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "fmi"

CONSUMED_WEATHER_DATA_FIELDS = frozenset(
    {
        "time",
        "temperature",
        "dew_point",
        "pressure",
        "humidity",
        "wind_direction",
        "wind_speed",
        "wind_max",
        "wind_gust",
        "symbol",
        "cloud_cover",
        "precipitation_amount",
    }
)
CONSUMED_VALUE_FIELDS = CONSUMED_WEATHER_DATA_FIELDS - {"time"}


class FMIContractError(ValueError):
    """Report a fixture or dependency shape that the integration cannot consume."""


def load_json_fixture(name: str) -> dict[str, Any]:
    """Load a compact synthetic FMI fixture."""
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def load_text_fixture(name: str) -> str:
    """Load an XML or text FMI fixture."""
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if value == "NaN":
        return math.nan
    return float(value)


def _value(spec: Any, default_spec: Mapping[str, Any] | None) -> models.Value:
    if isinstance(spec, Mapping):
        value = spec.get("value")
        unit = spec.get("unit", "")
    else:
        value = spec
        unit = default_spec.get("unit", "") if default_spec else ""
    return models.Value(_number(value), str(unit))


def weather_data_from_payload(
    payload: Mapping[str, Any],
    defaults: Mapping[str, Mapping[str, Any]],
) -> models.WeatherData:
    """Build the real client model while validating every consumed field."""
    values = payload.get("values")
    if not isinstance(values, Mapping):
        raise FMIContractError("FMI weather sample must contain a 'values' mapping")

    missing = sorted(CONSUMED_VALUE_FIELDS - (defaults.keys() | values.keys()))
    if missing:
        raise FMIContractError(f"missing FMI weather fields: {', '.join(missing)}")

    raw_time = payload.get("time")
    if not isinstance(raw_time, str):
        raise FMIContractError("FMI weather sample must contain an ISO-8601 'time' string")
    timestamp = datetime.fromisoformat(raw_time)
    if timestamp.tzinfo is None:
        raise FMIContractError("FMI weather sample timestamp must be timezone-aware")

    model_values: dict[str, models.Value] = {}
    for field in models.WeatherData._fields:
        if field == "time":
            continue
        default_spec = defaults.get(field)
        spec = values.get(field, default_spec or {"value": None, "unit": ""})
        model_values[field] = _value(spec, default_spec)

    return models.WeatherData(time=timestamp, **model_values)


def forecast_from_fixture(name: str, series: str = "forecasts") -> models.Forecast:
    """Build a Forecast from a named series in a fixture."""
    fixture = load_json_fixture(name)
    defaults = fixture.get("defaults", {})
    samples = fixture.get(series)
    if isinstance(samples, Mapping):
        raw_start = samples.get("start")
        count = samples.get("count")
        overrides = samples.get("overrides", {})
        if not isinstance(raw_start, str) or not isinstance(count, int):
            raise FMIContractError(
                f"generated FMI fixture series '{series}' requires string 'start' and int 'count'"
            )
        start = datetime.fromisoformat(raw_start)
        samples = [
            {
                "time": (start + timedelta(hours=index)).isoformat(),
                "values": overrides.get(str(index), {}),
            }
            for index in range(count)
        ]
    if not isinstance(samples, list):
        raise FMIContractError(f"FMI fixture series '{series}' must be a list or generated mapping")
    return models.Forecast(
        place=fixture["place"],
        lat=float(fixture["lat"]),
        lon=float(fixture["lon"]),
        forecasts=[weather_data_from_payload(sample, defaults) for sample in samples],
    )


def weather_from_fixture(name: str, sample: str = "current") -> models.Weather | None:
    """Build a Weather from a named sample in a fixture."""
    fixture = load_json_fixture(name)
    payload = fixture.get(sample)
    if payload is None:
        return None
    return models.Weather(
        place=fixture["place"],
        lat=float(fixture["lat"]),
        lon=float(fixture["lon"]),
        data=weather_data_from_payload(payload, fixture.get("defaults", {})),
    )


class FakeFMIClient:
    """Narrow async fake for the FMI methods consumed by the integration."""

    def __init__(
        self,
        *,
        weather: models.Weather | None = None,
        forecast: models.Forecast | None = None,
        observation: models.Weather | None = None,
        place_observation: models.Weather | None = None,
        weather_error: Exception | None = None,
        forecast_error: Exception | None = None,
        observation_error: Exception | None = None,
        place_observation_error: Exception | None = None,
    ) -> None:
        self.weather = weather
        self.forecast = forecast
        self.observation = observation
        self.place_observation = place_observation
        self.weather_error = weather_error
        self.forecast_error = forecast_error
        self.observation_error = observation_error
        self.place_observation_error = place_observation_error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def async_weather_by_coordinates(
        self, latitude: float, longitude: float
    ) -> models.Weather | None:
        self.calls.append(("weather", (latitude, longitude)))
        if self.weather_error:
            raise self.weather_error
        return self.weather

    async def async_forecast_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        timestep_hours: int,
        forecast_points: int,
    ) -> models.Forecast | None:
        self.calls.append(("forecast", (latitude, longitude, timestep_hours, forecast_points)))
        if self.forecast_error:
            raise self.forecast_error
        return self.forecast

    async def async_observation_by_station_id(self, station_id: int) -> models.Weather | None:
        self.calls.append(("observation", (station_id,)))
        if self.observation_error:
            raise self.observation_error
        return self.observation

    async def async_observation_by_place(self, place: str) -> models.Weather | None:
        self.calls.append(("observation_by_place", (place,)))
        if self.place_observation_error:
            raise self.place_observation_error
        return self.place_observation
