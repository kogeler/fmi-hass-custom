# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Pure local geometry for FMI lightning observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from homeassistant.util.location import distance as ha_distance

_DIRECTION_SECTORS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


@dataclass(frozen=True, slots=True)
class LightningGeometry:
    """Validated local presentation geometry for one lightning group."""

    distance_metres: float
    distance: float
    bearing: float | None
    direction: str


def direction_from_bearing(bearing: float) -> str:
    """Return the half-open eight-sector compass token for a bearing."""
    if isinstance(bearing, bool) or not isinstance(bearing, Real):
        raise ValueError("bearing must be a finite number")
    numeric_bearing = float(bearing)
    if not math.isfinite(numeric_bearing):
        raise ValueError("bearing must be a finite number")
    normalized = numeric_bearing % 360.0
    return _DIRECTION_SECTORS[int((normalized + 22.5) // 45.0) % len(_DIRECTION_SECTORS)]


def lightning_geometry(
    reference_latitude: float,
    reference_longitude: float,
    target_latitude: float,
    target_longitude: float,
) -> LightningGeometry | None:
    """Calculate local WGS84 distance and initial great-circle bearing."""
    values = (
        reference_latitude,
        reference_longitude,
        target_latitude,
        target_longitude,
    )
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        return None
    reference_latitude, reference_longitude, target_latitude, target_longitude = (
        float(value) for value in values
    )
    if (
        not all(math.isfinite(value) for value in values)
        or not -90 <= reference_latitude <= 90
        or not -180 <= reference_longitude <= 180
        or not -90 <= target_latitude <= 90
        or not -180 <= target_longitude <= 180
    ):
        return None

    distance_metres = ha_distance(
        reference_latitude,
        reference_longitude,
        target_latitude,
        target_longitude,
    )
    if distance_metres is None or not math.isfinite(distance_metres) or distance_metres < 0:
        return None
    if distance_metres == 0:
        return LightningGeometry(
            distance_metres=0.0,
            distance=0.0,
            bearing=None,
            direction="here",
        )

    latitude_1 = math.radians(reference_latitude)
    latitude_2 = math.radians(target_latitude)
    longitude_delta = math.radians((target_longitude - reference_longitude + 540.0) % 360.0 - 180.0)
    bearing = (
        math.degrees(
            math.atan2(
                math.sin(longitude_delta) * math.cos(latitude_2),
                math.cos(latitude_1) * math.sin(latitude_2)
                - math.sin(latitude_1) * math.cos(latitude_2) * math.cos(longitude_delta),
            )
        )
        % 360.0
    )
    direction = direction_from_bearing(bearing)
    return LightningGeometry(
        distance_metres=distance_metres,
        distance=round(distance_metres / 1000.0, 2),
        bearing=round(bearing, 1) % 360.0,
        direction=direction,
    )
