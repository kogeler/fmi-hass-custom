# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Deterministic selection of the best remaining FMI forecast hour."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

import fmi_weather_client.models as fmi_models

from . import const, utils
from .fmi_client import ForecastProbabilities


@dataclass(frozen=True, slots=True)
class BestCondition:
    """Represent one selected hour or an explicitly empty calculation outcome."""

    status: str
    time: datetime | None = None
    temperature: float | None = None
    apparent_temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    thunderstorm_probability: float | None = None


@dataclass(frozen=True, slots=True)
class BestTimeLimits:
    """Keep persisted inclusive Best-time limits together."""

    minimum_temperature: float
    maximum_temperature: float
    minimum_humidity: float
    maximum_humidity: float
    minimum_wind_speed: float
    maximum_wind_speed: float
    minimum_precipitation: float
    maximum_precipitation: float

    @property
    def temperature_midpoint(self) -> float:
        """Return the midpoint used for perceived-temperature ordering."""
        return (self.minimum_temperature + self.maximum_temperature) / 2

    def accepts(self, candidate: _Candidate, allowed_symbols: Collection[int]) -> bool:
        """Return whether a complete candidate passes every inclusive hard gate."""
        return candidate.symbol in allowed_symbols and all(
            (
                self.minimum_temperature
                <= candidate.apparent_temperature
                <= self.maximum_temperature,
                self.minimum_humidity <= candidate.humidity <= self.maximum_humidity,
                self.minimum_wind_speed <= candidate.wind_speed <= self.maximum_wind_speed,
                self.minimum_precipitation <= candidate.precipitation <= self.maximum_precipitation,
            )
        )


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Keep one complete forecast hour and every ordering input."""

    time: datetime
    symbol: int
    temperature: float
    apparent_temperature: float
    humidity: float
    wind_speed: float
    precipitation: float
    precipitation_probability: float
    thunderstorm_probability: float

    def sort_key(self, temperature_midpoint: float) -> tuple[float, float, float, float, datetime]:
        """Return thunder, thermal, PoP, amount, and time in frozen priority order."""
        return (
            self.thunderstorm_probability,
            abs(self.apparent_temperature - temperature_midpoint),
            self.precipitation_probability,
            self.precipitation,
            self.time,
        )

    def as_condition(self) -> BestCondition:
        """Return this candidate as the selected coordinator result."""
        return BestCondition(
            status=const.BEST_CONDITION_AVAIL,
            time=self.time,
            temperature=self.temperature,
            apparent_temperature=self.apparent_temperature,
            humidity=self.humidity,
            wind_speed=self.wind_speed,
            precipitation=self.precipitation,
            precipitation_probability=self.precipitation_probability,
            thunderstorm_probability=self.thunderstorm_probability,
        )


def _complete_candidate(
    sample: fmi_models.WeatherData,
    local_time: datetime,
    probabilities: ForecastProbabilities,
) -> _Candidate | None:
    """Return one complete candidate without applying user preference gates."""
    symbol = _finite_value(sample, "symbol")
    temperature = _finite_value(sample, "temperature")
    apparent_temperature = _finite_value(sample, "feels_like")
    humidity = _finite_value(sample, "humidity")
    wind_speed = _finite_value(sample, "wind_speed")
    precipitation = _finite_value(sample, "precipitation_amount")
    precipitation_probability = utils.finite_float(probabilities.precipitation)
    thunderstorm_probability = utils.finite_float(probabilities.thunderstorm)
    required = (
        symbol,
        temperature,
        apparent_temperature,
        humidity,
        wind_speed,
        precipitation,
        precipitation_probability,
        thunderstorm_probability,
    )
    if any(value is None for value in required):
        return None
    if not all(
        0 <= cast(float, value) <= 100
        for value in (precipitation_probability, thunderstorm_probability)
    ):
        return None
    numeric_symbol = cast(float, symbol)
    if not numeric_symbol.is_integer():
        return None
    return _Candidate(
        time=local_time,
        symbol=int(numeric_symbol),
        temperature=cast(float, temperature),
        apparent_temperature=cast(float, apparent_temperature),
        humidity=cast(float, humidity),
        wind_speed=cast(float, wind_speed),
        precipitation=cast(float, precipitation),
        precipitation_probability=cast(float, precipitation_probability),
        thunderstorm_probability=cast(float, thunderstorm_probability),
    )


def _finite_value(sample: object, name: str) -> float | None:
    """Return one finite FMI model value."""
    wrapped = getattr(sample, name, None)
    return utils.finite_float(getattr(wrapped, "value", None))


def select_best_condition(
    forecasts: Sequence[fmi_models.WeatherData],
    probability_at: Callable[[object], ForecastProbabilities],
    now: datetime,
    limits: BestTimeLimits,
    allowed_symbols: Collection[int],
) -> BestCondition:
    """Select one remaining current-local-day hour or classify the empty outcome."""
    if not forecasts or (local_now := utils.as_local_aware_datetime(now)) is None:
        return BestCondition(const.BEST_CONDITION_NOT_AVAIL)

    timestamped_samples = 0
    remaining_samples = 0
    complete_samples = 0
    candidates: list[_Candidate] = []
    for sample in forecasts:
        local_time = utils.as_local_aware_datetime(getattr(sample, "time", None))
        if local_time is None:
            continue
        timestamped_samples += 1
        if local_time.date() != local_now.date() or local_time < local_now:
            continue
        remaining_samples += 1
        candidate = _complete_candidate(
            sample,
            local_time,
            probability_at(getattr(sample, "time", None)),
        )
        if candidate is None:
            continue
        complete_samples += 1
        if limits.accepts(candidate, allowed_symbols):
            candidates.append(candidate)

    if candidates:
        return min(
            candidates,
            key=lambda candidate: candidate.sort_key(limits.temperature_midpoint),
        ).as_condition()
    if timestamped_samples and (not remaining_samples or complete_samples):
        return BestCondition(const.BEST_CONDITION_NO_SUITABLE)
    return BestCondition(const.BEST_CONDITION_NOT_AVAIL)
