# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Narrow compatibility boundary for the selected FMI weather client."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import fmi_weather_client as upstream
from fmi_weather_client import models

from .xml_parser import (
    ensure_safe_expat,
    iter_xml_elements,
    parse_xml_document,
    xml_attribute,
    xml_text,
)

FORECAST_GUST_PARAMETER = "HourlyMaximumGust"


@dataclass(frozen=True, slots=True)
class PlaceResolution:
    """Validated location fields needed by the config flow."""

    place: str
    latitude: float
    longitude: float


class _UpstreamPrivacyFilter(logging.Filter):
    """Drop dependency records that contain coordinates or full FMI responses."""

    _fmi_privacy_filter = True

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name == "fmi_weather_client.http"
            and record.msg == "GET request to %s. Parameters: %s"
        ):
            return False
        if record.name != "fmi_weather_client.parsers.forecast":
            return True
        if record.msg == "Received place: %s (%d, %d)":
            return False
        if not isinstance(record.msg, str):
            return False
        return not record.msg.lstrip().startswith("<")


def _install_upstream_privacy_filters() -> None:
    """Install idempotent filters on the two dependency loggers with private data."""
    for logger_name in (
        "fmi_weather_client.http",
        "fmi_weather_client.parsers.forecast",
    ):
        logger = logging.getLogger(logger_name)
        if any(getattr(item, "_fmi_privacy_filter", False) for item in logger.filters):
            continue
        logger.addFilter(_UpstreamPrivacyFilter())


_install_upstream_privacy_filters()


async def async_observation_by_place(place: str) -> models.Weather | None:
    """Call the upstream place observation only on a safe XML runtime."""
    ensure_safe_expat()
    return await upstream.async_observation_by_place(place)


async def async_observation_by_station_id(station_id: int) -> models.Weather | None:
    """Call the upstream station observation only on a safe XML runtime."""
    ensure_safe_expat()
    return await upstream.async_observation_by_station_id(station_id)


def _place_coordinate(value: Any, *, minimum: float, maximum: float) -> float:
    """Validate one coordinate returned by the selected FMI client."""
    if isinstance(value, bool):
        raise TypeError("FMI place coordinate must be numeric")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError("FMI place coordinate is outside WGS84")
    return number


def _resolve_place(place: str) -> PlaceResolution | None:
    """Resolve one name after bounding XML before the selected parser runs."""
    body = upstream.http.request_weather_by_place(place)
    parse_xml_document(body)
    forecast = upstream.forecast_parser.parse_fmi_response(body, models.RequestType.WEATHER)
    if not forecast.forecasts:
        return None
    canonical_place = forecast.place
    if not isinstance(canonical_place, str) or not (canonical_place := canonical_place.strip()):
        raise ValueError("FMI place result has no canonical name")
    return PlaceResolution(
        place=canonical_place,
        latitude=_place_coordinate(forecast.lat, minimum=-90, maximum=90),
        longitude=_place_coordinate(forecast.lon, minimum=-180, maximum=180),
    )


async def async_resolve_place(place: str) -> PlaceResolution | None:
    """Resolve a place with bounded parsing outside the event loop."""
    return await asyncio.to_thread(_resolve_place, place)


def _finite_number(value: Any) -> float | None:
    """Return a finite float without turning missing data into zero."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def _hourly_gusts_by_time(body: str) -> dict[datetime, float | None]:
    """Extract the forecast producer's hourly gust field from a WFS response."""
    document = parse_xml_document(body)
    field_names = [
        xml_attribute(field, "name") or "" for field in iter_xml_elements(document, "field")
    ]
    if FORECAST_GUST_PARAMETER not in field_names:
        return {}
    gust_index = field_names.index(FORECAST_GUST_PARAMETER)

    positions = next(
        (
            text
            for node in iter_xml_elements(document, "positions")
            if (text := xml_text(node)) is not None
        ),
        "",
    )
    value_sets = next(
        (
            text
            for node in iter_xml_elements(document, "doubleOrNilReasonTupleList")
            if (text := xml_text(node)) is not None
        ),
        "",
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
