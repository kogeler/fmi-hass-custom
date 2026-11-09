# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/WARNINGS.md

"""Bounded validation of simple planar CAP rings before local point matching."""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass

MAX_GEOMETRY_COMPARISONS = 1_000_000
type Point = tuple[float, float]


class WarningGeometryError(ValueError):
    """Reject ambiguous or excessively complex source geometry."""

    def __init__(self, message: str, *, reason: str = "invalid_snapshot") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class _Segment:
    bounds: tuple[float, float, float, float]
    index: int
    start: Point
    end: Point


def _segments(ring: tuple[Point, ...]) -> list[_Segment]:
    return [
        _Segment((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])), i, a, b)
        for i, (a, b) in enumerate(zip(ring, ring[1:], strict=False))
    ]


def _sweep_candidates(segments: list[_Segment], axis: int) -> int:
    """Return the exact active-pair visits of a sweep along one axis without performing it."""
    lows = sorted(segment.bounds[2 * axis] for segment in segments)
    highs = sorted(segment.bounds[2 * axis + 1] for segment in segments)
    return sum(position - bisect_left(highs, low) for position, low in enumerate(lows))


def _validate_intersections(segments: list[_Segment]) -> None:
    costs = [_sweep_candidates(segments, axis) for axis in (0, 1)]
    axis = costs.index(min(costs))
    if costs[axis] > MAX_GEOMETRY_COMPARISONS:
        raise WarningGeometryError(
            "geometry comparison budget exceeded", reason="geometry_too_complex"
        )
    low, high, other_low, other_high = 2 * axis, 2 * axis + 1, 2 - 2 * axis, 3 - 2 * axis
    active: list[_Segment] = []
    for segment in sorted(segments, key=lambda item: item.bounds[low]):
        active = [other for other in active if other.bounds[high] >= segment.bounds[low]]
        for other in active:
            if abs(segment.index - other.index) in (1, len(segments) - 1):
                continue
            if (
                segment.bounds[other_low] > other.bounds[other_high]
                or other.bounds[other_low] > segment.bounds[other_high]
            ):
                continue
            if _edges_intersect(segment.start, segment.end, other.start, other.end):
                raise WarningGeometryError("intersecting edges")
        active.append(segment)


def _edges_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def _cross(first: Point, second: Point, third: Point) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (
        third[0] - first[0]
    )


def validate_ring(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """Normalize zero-length edges and reject degenerate/non-simple rings with bounded work."""
    ring = tuple(
        point for index, point in enumerate(points) if not index or point != points[index - 1]
    )
    vertices = ring[:-1]
    if len(set(vertices)) != len(vertices):
        raise WarningGeometryError("self-touching ring")
    origin = ring[0]
    if not math.fsum(
        _cross(origin, first, second) for first, second in zip(ring, ring[1:], strict=False)
    ):
        raise WarningGeometryError("zero-area ring")
    for index, middle in enumerate(vertices):
        previous, following = vertices[index - 1], ring[index + 1]
        if _cross(previous, middle, following) == 0 and (
            (previous[0] - middle[0]) * (following[0] - middle[0])
            + (previous[1] - middle[1]) * (following[1] - middle[1])
            > 0
        ):
            raise WarningGeometryError("overlapping adjacent edges")
    _validate_intersections(_segments(ring))
    return ring
