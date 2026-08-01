# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Stable contract assertions shared by marker-isolated live FMI tests."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any


class LiveContractError(AssertionError):
    """Identify upstream shape/value drift with an actionable test message."""


MODEL_RANGES = {
    "temperature": (-90.0, 60.0),
    "dew_point": (-100.0, 60.0),
    "pressure": (800.0, 1200.0),
    "humidity": (0.0, 100.0),
    "wind_direction": (0.0, 360.0),
    "wind_speed": (0.0, 120.0),
    "wind_gust": (0.0, 150.0),
    "wind_max": (0.0, 150.0),
    "precipitation_amount": (-1.0, 500.0),
    "cloud_cover": (0.0, 100.0),
    "symbol": (0.0, 100.0),
}

HA_FORECAST_RANGES = {
    "temperature": (-90.0, 60.0),
    "templow": (-90.0, 60.0),
    "dew_point": (-100.0, 60.0),
    "pressure": (800.0, 1200.0),
    "humidity": (0.0, 100.0),
    "wind_bearing": (0.0, 360.0),
    "wind_speed": (0.0, 500.0),
    "wind_gust_speed": (0.0, 600.0),
    "precipitation": (0.0, 500.0),
    "cloud_coverage": (0.0, 100.0),
}


def aware_timestamp(value: object, label: str) -> datetime:
    """Return one aware timestamp or raise a classified contract error."""
    if not isinstance(value, datetime):
        raise LiveContractError(f"{label} timestamp is not a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveContractError(f"{label} timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _finite_model_values(sample: object, label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for field, (minimum, maximum) in MODEL_RANGES.items():
        wrapped = getattr(sample, field, None)
        raw = getattr(wrapped, "value", None)
        if raw is None:
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError) as error:
            raise LiveContractError(f"{label} {field} is not numeric: {raw!r}") from error
        if math.isnan(number):
            continue
        if not math.isfinite(number):
            raise LiveContractError(f"{label} {field} is not finite: {raw!r}")
        if not minimum <= number <= maximum:
            raise LiveContractError(
                f"{label} {field}={number} is outside broad range {minimum}..{maximum}"
            )
        values[field] = number
    return values


def validate_model_forecast(forecast: object, label: str) -> Sequence[Any]:
    """Validate an installed-client forecast without asserting exact weather."""
    place = getattr(forecast, "place", None)
    if not isinstance(place, str) or not place.strip():
        raise LiveContractError(f"{label} place is missing")
    samples = getattr(forecast, "forecasts", None)
    if not isinstance(samples, Sequence) or isinstance(samples, str) or not samples:
        raise LiveContractError(f"{label} forecast contains no samples")

    previous: datetime | None = None
    usable_samples = 0
    for index, sample in enumerate(samples):
        sample_label = f"{label} sample {index}"
        timestamp = aware_timestamp(getattr(sample, "time", None), sample_label)
        if previous is not None and timestamp <= previous:
            raise LiveContractError(f"{sample_label} timestamp is not strictly ordered")
        previous = timestamp
        values = _finite_model_values(sample, sample_label)
        if values.keys() & {"temperature", "pressure", "humidity", "wind_speed"}:
            usable_samples += 1
    if not usable_samples:
        raise LiveContractError(f"{label} has no usable meteorological samples")
    return samples


def validate_model_weather(
    weather: object,
    label: str,
    *,
    max_age: timedelta,
    now: datetime | None = None,
) -> Any:
    """Validate one current/observation model and its source freshness."""
    if weather is None:
        raise LiveContractError(f"{label} returned no weather")
    place = getattr(weather, "place", None)
    if not isinstance(place, str) or not place.strip():
        raise LiveContractError(f"{label} place is missing")
    sample = getattr(weather, "data", None)
    if sample is None:
        raise LiveContractError(f"{label} data is missing")
    timestamp = aware_timestamp(getattr(sample, "time", None), label)
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    if timestamp < reference - max_age:
        raise LiveContractError(
            f"{label} is stale: {timestamp.isoformat()} is older than {max_age}"
        )
    if timestamp > reference + timedelta(hours=2):
        raise LiveContractError(f"{label} timestamp is implausibly far in the future")
    values = _finite_model_values(sample, label)
    if not values.keys() & {"temperature", "pressure", "humidity", "wind_speed"}:
        raise LiveContractError(f"{label} has no usable meteorological values")
    return sample


def validate_ha_forecast(
    items: object,
    label: str,
) -> list[tuple[datetime, Mapping[str, Any]]]:
    """Validate Home Assistant service output consumed by dashboards."""
    if not isinstance(items, list) or not items:
        raise LiveContractError(f"{label} Home Assistant forecast is empty")
    validated: list[tuple[datetime, Mapping[str, Any]]] = []
    previous: datetime | None = None
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise LiveContractError(f"{label} item {index} is not a mapping")
        raw_timestamp = item.get("datetime")
        try:
            parsed = datetime.fromisoformat(str(raw_timestamp))
        except ValueError as error:
            raise LiveContractError(
                f"{label} item {index} has invalid datetime {raw_timestamp!r}"
            ) from error
        timestamp = aware_timestamp(parsed, f"{label} item {index}")
        if previous is not None and timestamp <= previous:
            raise LiveContractError(f"{label} item {index} is not strictly ordered")
        previous = timestamp
        finite_values = 0
        for field, (minimum, maximum) in HA_FORECAST_RANGES.items():
            raw = item.get(field)
            if raw is None:
                continue
            try:
                number = float(raw)
            except (TypeError, ValueError) as error:
                raise LiveContractError(
                    f"{label} item {index} {field} is not numeric: {raw!r}"
                ) from error
            if not math.isfinite(number) or not minimum <= number <= maximum:
                raise LiveContractError(
                    f"{label} item {index} {field}={raw!r} is not finite/plausible"
                )
            finite_values += 1
        if not finite_values:
            raise LiveContractError(f"{label} item {index} has no usable numeric values")
        validated.append((timestamp, item))
    return validated
