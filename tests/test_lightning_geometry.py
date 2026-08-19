# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Independent reference and edge tests for local lightning geometry."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.fmi import lightning as lightning_module
from custom_components.fmi.lightning import direction_from_bearing, lightning_geometry
from custom_components.fmi.utils import get_bounding_box


# WGS84 distances are frozen from GeographicLib's Geodesic.WGS84 inverse solver. Expected
# bearings use the independently evaluated spherical initial-bearing formula frozen by D005.
# https://geographiclib.sourceforge.io/html/python/code.html
@pytest.mark.parametrize(
    ("start", "end", "expected_distance", "expected_bearing", "expected_direction"),
    [
        ((60.17, 24.94), (60.20, 24.90), 4.01, 326.5, "NW"),
        ((0.0, 179.9), (0.0, -179.9), 22.26, 90.0, "E"),
        ((0.0, -179.9), (0.0, 179.9), 22.26, 270.0, "W"),
        ((89.0, 0.0), (89.0, 90.0), 157.95, 45.0, "NE"),
        ((-89.0, 0.0), (-89.0, -90.0), 157.95, 225.0, "SW"),
        ((80.0, 90.0), (90.0, 0.0), 1116.83, 0.0, "N"),
        ((90.0, 0.0), (80.0, 90.0), 1116.83, 90.0, "E"),
    ],
)
def test_lightning_geometry_matches_frozen_reference_vectors(
    start: tuple[float, float],
    end: tuple[float, float],
    expected_distance: float,
    expected_bearing: float,
    expected_direction: str,
) -> None:
    """Calculate finite WGS84 distance and normalized initial bearing."""
    geometry = lightning_geometry(*start, *end)

    assert geometry is not None
    assert geometry.distance == expected_distance
    assert geometry.bearing == expected_bearing
    assert geometry.direction == expected_direction


@pytest.mark.parametrize(
    ("bearing", "expected"),
    [
        (22.5 - 1e-9, "N"),
        (22.5, "NE"),
        (22.5 + 1e-9, "NE"),
        (67.5 - 1e-9, "NE"),
        (67.5, "E"),
        (67.5 + 1e-9, "E"),
        (112.5 - 1e-9, "E"),
        (112.5, "SE"),
        (112.5 + 1e-9, "SE"),
        (157.5 - 1e-9, "SE"),
        (157.5, "S"),
        (157.5 + 1e-9, "S"),
        (202.5 - 1e-9, "S"),
        (202.5, "SW"),
        (202.5 + 1e-9, "SW"),
        (247.5 - 1e-9, "SW"),
        (247.5, "W"),
        (247.5 + 1e-9, "W"),
        (292.5 - 1e-9, "W"),
        (292.5, "NW"),
        (292.5 + 1e-9, "NW"),
        (337.5 - 1e-9, "NW"),
        (337.5, "N"),
        (337.5 + 1e-9, "N"),
        (-45.0, "NW"),
        (360.0, "N"),
        (720.0, "N"),
    ],
)
def test_direction_sector_boundaries_are_half_open(bearing: float, expected: str) -> None:
    """Keep every exact compass edge deterministic before bearing rounding."""
    assert direction_from_bearing(bearing) == expected


@pytest.mark.parametrize("bearing", [True, False, float("nan"), float("inf"), "90"])
def test_direction_rejects_non_finite_or_non_numeric_values(bearing: Any) -> None:
    """Never coerce booleans, strings, NaN, or infinities into a direction."""
    with pytest.raises(ValueError, match="finite number"):
        direction_from_bearing(bearing)


def test_coincident_lightning_has_no_invented_bearing() -> None:
    """Represent a zero-distance group without claiming arbitrary north."""
    geometry = lightning_geometry(60.17, 24.94, 60.17, 24.94)

    assert geometry is not None
    assert geometry.distance_metres == 0.0
    assert geometry.distance == 0.0
    assert geometry.bearing is None
    assert geometry.direction == "here"


@pytest.mark.parametrize(
    "coordinates",
    [
        (True, 0.0, 0.0, 0.0),
        (0.0, False, 0.0, 0.0),
        (91.0, 0.0, 0.0, 0.0),
        (0.0, 181.0, 0.0, 0.0),
        (0.0, 0.0, -91.0, 0.0),
        (0.0, 0.0, 0.0, -181.0),
        (float("nan"), 0.0, 0.0, 0.0),
        (0.0, float("inf"), 0.0, 0.0),
    ],
)
def test_lightning_geometry_rejects_invalid_coordinates(
    coordinates: tuple[Any, Any, Any, Any],
) -> None:
    """Reject unsafe inputs before trigonometry without coordinate output."""
    assert lightning_geometry(*coordinates) is None


@pytest.mark.parametrize("result", [None, -1.0, float("nan"), float("inf")])
def test_lightning_geometry_rejects_distance_failure(monkeypatch, result: float | None) -> None:
    """Treat HA distance non-convergence or invalid results as unusable rows."""
    monkeypatch.setattr(lightning_module, "ha_distance", lambda *_args: result)

    assert lightning_geometry(0.0, 0.0, 1.0, 1.0) is None


def test_lightning_bbox_corner_exceeds_advertised_radius() -> None:
    """Characterize why the square FMI prefilter cannot enforce a circular radius."""
    radius_km = 200
    latitude = 60.17
    longitude = 24.94
    bbox = get_bounding_box(latitude, longitude, half_side_in_km=radius_km)
    geometry = lightning_geometry(latitude, longitude, bbox.lat_max, bbox.lon_max)

    assert geometry is not None
    assert geometry.distance_metres > radius_km * 1000
