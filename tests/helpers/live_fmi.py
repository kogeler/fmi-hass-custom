# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Stable contract assertions shared by marker-isolated live FMI tests."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util


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
    "cloud_low_cover": (0.0, 100.0),
    "cloud_mid_cover": (0.0, 100.0),
    "cloud_high_cover": (0.0, 100.0),
    "feels_like": (-120.0, 80.0),
    "symbol": (0.0, 100.0),
}

HA_FORECAST_RANGES = {
    "temperature": (-90.0, 60.0),
    "apparent_temperature": (-120.0, 80.0),
    "templow": (-90.0, 60.0),
    "dew_point": (-100.0, 60.0),
    "pressure": (800.0, 1200.0),
    "humidity": (0.0, 100.0),
    "wind_bearing": (0.0, 360.0),
    "wind_speed": (0.0, 500.0),
    "wind_gust_speed": (0.0, 600.0),
    "precipitation": (0.0, 500.0),
    "precipitation_probability": (0.0, 100.0),
    "cloud_coverage": (0.0, 100.0),
}

HA_FORECAST_PRECIPITATION_HALF_STEP = 0.005
HELSINKI = ZoneInfo("Europe/Helsinki")


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


def validate_probabilities(probabilities: object, label: str) -> tuple[float, float]:
    """Require two finite FMI forecast probabilities in their native percentage range."""
    validated: list[float] = []
    for field in ("precipitation", "thunderstorm"):
        raw = getattr(probabilities, field, None)
        try:
            number = float(cast(Any, raw))
        except (TypeError, ValueError) as error:
            raise LiveContractError(
                f"{label} {field} probability is not numeric: {raw!r}"
            ) from error
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise LiveContractError(f"{label} {field} probability={raw!r} is outside 0..100")
        validated.append(number)
    return validated[0], validated[1]


def validate_first_available_local_day_probability_supplements(
    samples: Sequence[Any],
    probabilities_by_time: Mapping[datetime, object],
    label: str,
    *,
    now: datetime | None = None,
) -> int:
    """Validate probabilities on the first represented future Helsinki-local date."""
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    future_samples: list[tuple[int, datetime]] = []
    for index, sample in enumerate(samples):
        timestamp = aware_timestamp(getattr(sample, "time", None), f"{label} sample {index}")
        if timestamp >= reference:
            future_samples.append((index, timestamp))
    if not future_samples:
        raise LiveContractError(f"{label} has no future samples")

    local_date = future_samples[0][1].astimezone(HELSINKI).date()
    validated = 0
    for index, timestamp in future_samples:
        if timestamp.astimezone(HELSINKI).date() != local_date:
            continue
        probabilities = probabilities_by_time.get(timestamp)
        if probabilities is None:
            raise LiveContractError(f"{label} sample {index} has no aligned probabilities")
        validate_probabilities(probabilities, f"{label} sample {index}")
        validated += 1
    return validated


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


def validate_first_available_local_day_ha_metrics(
    hourly: Sequence[tuple[datetime, Mapping[str, Any]]],
    label: str,
    *,
    now: datetime | None = None,
) -> int:
    """Require apparent temperature and PoP on the first future Helsinki-local date."""
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    future_items = [item for item in hourly if item[0] >= reference]
    if not future_items:
        raise LiveContractError(f"{label} has no future items")

    local_date = future_items[0][0].astimezone(HELSINKI).date()
    validated = 0
    for index, (timestamp, item) in enumerate(future_items):
        if timestamp.astimezone(HELSINKI).date() != local_date:
            continue
        for field in ("apparent_temperature", "precipitation_probability"):
            raw = item.get(field)
            try:
                number = float(cast(Any, raw))
            except (TypeError, ValueError) as error:
                raise LiveContractError(
                    f"{label} item {index} {field} is not numeric: {raw!r}"
                ) from error
            minimum, maximum = HA_FORECAST_RANGES[field]
            if not math.isfinite(number) or not minimum <= number <= maximum:
                raise LiveContractError(
                    f"{label} item {index} {field}={raw!r} is not finite/plausible"
                )
        validated += 1
    return validated


def validate_daily_precipitation(
    hourly: Sequence[tuple[datetime, Mapping[str, Any]]],
    daily: Sequence[tuple[datetime, Mapping[str, Any]]],
) -> None:
    """Validate daily sums after Home Assistant independently rounds service values."""
    hourly_by_day: defaultdict[date, list[float]] = defaultdict(list)
    for timestamp, item in hourly:
        precipitation = item.get("precipitation")
        if precipitation is not None:
            hourly_by_day[dt_util.as_local(timestamp).date()].append(float(precipitation))

    compared_days = 0
    for timestamp, item in daily:
        values = hourly_by_day[dt_util.as_local(timestamp).date()]
        if not values:
            continue
        compared_days += 1
        raw_daily = item.get("precipitation")
        if not isinstance(raw_daily, int | float | str):
            raise LiveContractError(f"daily precipitation is not numeric: {raw_daily!r}")
        try:
            daily_value = float(raw_daily)
        except (TypeError, ValueError) as error:
            raise LiveContractError(f"daily precipitation is not numeric: {raw_daily!r}") from error
        expected = math.fsum(values)
        rounding_tolerance = HA_FORECAST_PRECIPITATION_HALF_STEP * (len(values) + 1)
        if not math.isfinite(daily_value) or not math.isclose(
            daily_value,
            expected,
            rel_tol=0.0,
            abs_tol=rounding_tolerance,
        ):
            raise LiveContractError(
                f"daily precipitation {daily_value} differs from displayed hourly sum "
                f"{expected} beyond the {rounding_tolerance} rounding bound"
            )
    if not compared_days:
        raise LiveContractError("no matching hourly/daily precipitation day was exposed")
