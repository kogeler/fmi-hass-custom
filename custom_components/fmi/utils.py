"""Common utilities for the FMI Weather and Sensor integrations."""

import math
from datetime import datetime
from typing import Any, cast

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from . import const


class BoundingBox:
    def __init__(self, lat_min=None, lon_min=None, lat_max=None, lon_max=None):
        self.lat_min = lat_min
        self.lon_min = lon_min
        self.lat_max = lat_max
        self.lon_max = lon_max


def get_bounding_box(latitude_in_degrees, longitude_in_degrees, half_side_in_km):
    """Calculate a finite WGS84 bounding box, including at either pole."""
    assert 0 < half_side_in_km
    assert -90.0 <= latitude_in_degrees <= 90.0
    assert -180.0 <= longitude_in_degrees <= 180.0

    radius = 6371
    # Radius of the parallel at given latitude
    parallel_radius = radius * math.cos(math.radians(latitude_in_degrees))

    lat_delta = math.degrees(half_side_in_km / radius)
    lat_min = max(-90.0, latitude_in_degrees - lat_delta)
    lat_max = min(90.0, latitude_in_degrees + lat_delta)
    if lat_min == -90.0 or lat_max == 90.0 or abs(parallel_radius) < 1e-9:
        lon_min, lon_max = -180.0, 180.0
    else:
        lon_delta = math.degrees(half_side_in_km / parallel_radius)
        if (
            lon_delta >= 180.0
            or longitude_in_degrees - lon_delta < -180.0
            or longitude_in_degrees + lon_delta > 180.0
        ):
            lon_min, lon_max = -180.0, 180.0
        else:
            lon_min = longitude_in_degrees - lon_delta
            lon_max = longitude_in_degrees + lon_delta

    box = BoundingBox()
    box.lat_min = lat_min
    box.lon_min = lon_min
    box.lat_max = lat_max
    box.lon_max = lon_max

    return box


def finite_float(value: object) -> float | None:
    """Return a finite number while rejecting booleans and malformed values."""
    if isinstance(value, bool):
        return None
    try:
        number = float(cast(Any, value))
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def as_local_aware_datetime(value: object) -> datetime | None:
    """Convert an aware datetime to Home Assistant local time."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return dt_util.as_local(value)


def get_weather_symbol(symbol: object, hass: HomeAssistant | None = None) -> str:
    """Get a weather symbol for the symbol value."""
    numeric_symbol = finite_float(symbol)
    if numeric_symbol is None or not numeric_symbol.is_integer():
        return ""
    symbol_code = int(numeric_symbol)
    ret_val = const.FMI_WEATHER_SYMBOL_MAP.get(symbol_code, "")

    if hass is None or symbol_code != 1:
        return ret_val

    now = dt_util.now()
    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, now.date())
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, now.date())
    local_now = as_local_aware_datetime(now)
    local_sunrise = as_local_aware_datetime(sunrise)
    local_sunset = as_local_aware_datetime(sunset)
    if local_now is None or local_sunrise is None or local_sunset is None:
        return ret_val

    if local_sunrise >= local_sunset:
        return ret_val

    if local_now <= local_sunrise or local_now >= local_sunset:
        return const.FMI_WEATHER_SYMBOL_MAP[0]

    return ret_val
