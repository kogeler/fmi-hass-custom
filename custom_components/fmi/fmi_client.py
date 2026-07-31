"""Narrow compatibility boundary for the selected FMI weather client."""

from __future__ import annotations

import asyncio
import math
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import fmi_weather_client as upstream
from fmi_weather_client import models

GML_NAMESPACE = "http://www.opengis.net/gml/3.2"
GMLCOV_NAMESPACE = "http://www.opengis.net/gmlcov/1.0"
SWE_NAMESPACE = "http://www.opengis.net/swe/2.0"
FORECAST_GUST_PARAMETER = "HourlyMaximumGust"

async_observation_by_place = upstream.async_observation_by_place
async_observation_by_station_id = upstream.async_observation_by_station_id


def _finite_number(value: Any) -> float | None:
    """Return a finite float without turning missing data into zero."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def _hourly_gusts_by_time(body: str) -> dict[datetime, float | None]:
    """Extract the forecast producer's hourly gust field from a WFS response."""
    root = ET.fromstring(body)
    field_names = [field.get("name", "") for field in root.findall(f".//{{{SWE_NAMESPACE}}}field")]
    if FORECAST_GUST_PARAMETER not in field_names:
        return {}
    gust_index = field_names.index(FORECAST_GUST_PARAMETER)

    positions = root.findtext(f".//{{{GMLCOV_NAMESPACE}}}positions", default="")
    value_sets = root.findtext(
        f".//{{{GML_NAMESPACE}}}doubleOrNilReasonTupleList",
        default="",
    )
    gusts: dict[datetime, float | None] = {}
    for position_line, value_line in zip(
        positions.splitlines(), value_sets.splitlines(), strict=False
    ):
        position_parts = position_line.split()
        values = value_line.split()
        if len(position_parts) < 3 or gust_index >= len(values):
            continue
        timestamp = datetime.fromtimestamp(int(position_parts[2]), UTC)
        gusts[timestamp] = _finite_number(values[gust_index])
    return gusts


def _parse_forecast_response(body: str, request_type: models.RequestType) -> models.Forecast:
    """Parse with upstream and normalize forecast gust semantics."""
    gusts = _hourly_gusts_by_time(body)
    forecast = upstream.forecast_parser.parse_fmi_response(body, request_type)
    normalized: list[models.WeatherData] = []
    for sample in forecast.forecasts:
        hourly_gust = gusts.get(sample.time.astimezone(UTC))
        native_gust = _finite_number(sample.wind_gust.value)
        selected_gust = hourly_gust if hourly_gust is not None else native_gust
        normalized.append(
            sample._replace(
                wind_gust=models.Value(selected_gust, "m/s"),
                wind_max=models.Value(hourly_gust, "m/s"),
            )
        )
    return forecast._replace(forecasts=normalized)


def _request_by_coordinates(
    request_type: models.RequestType,
    latitude: float,
    longitude: float,
    timestep_minutes: int,
    forecast_points: int,
) -> models.Forecast:
    """Make the selected client's request with the supported forecast gust field."""
    params = upstream.http._create_params(  # pylint: disable=protected-access
        request_type,
        timestep_minutes,
        forecast_points,
        lat=latitude,
        lon=longitude,
    )
    parameters = params.get("parameters")
    if not isinstance(parameters, str):
        raise TypeError("fmi-weather-client returned non-string WFS parameters")
    parameter_names = parameters.split(",")
    if FORECAST_GUST_PARAMETER not in parameter_names:
        insert_at = (
            parameter_names.index("WindGust") + 1
            if "WindGust" in parameter_names
            else len(parameter_names)
        )
        parameter_names.insert(insert_at, FORECAST_GUST_PARAMETER)
        params["parameters"] = ",".join(parameter_names)
    body = upstream.http._send_request(params)  # pylint: disable=protected-access
    return _parse_forecast_response(body, request_type)


async def async_weather_by_coordinates(
    latitude: float,
    longitude: float,
) -> models.Weather | None:
    """Return forecast-current weather with a valid hourly gust when supplied."""
    forecast = await asyncio.to_thread(
        _request_by_coordinates,
        models.RequestType.WEATHER,
        latitude,
        longitude,
        10,
        4,
    )
    if not forecast.forecasts:
        return None
    return models.Weather(
        forecast.place,
        forecast.lat,
        forecast.lon,
        forecast.forecasts[-1],
    )


async def async_forecast_by_coordinates(
    latitude: float,
    longitude: float,
    timestep_hours: int,
    forecast_points: int,
) -> models.Forecast:
    """Return point forecasts with normalized gust values."""
    return await asyncio.to_thread(
        _request_by_coordinates,
        models.RequestType.FORECAST,
        latitude,
        longitude,
        timestep_hours * 60,
        forecast_points,
    )
