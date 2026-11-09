# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/WARNINGS.md, docs/contracts/COMPATIBILITY_SECURITY.md

"""Bounded, namespace-aware FMI CAP snapshots without a GIS dependency."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from . import const
from .warning_geometry import Point, WarningGeometryError, validate_ring
from .xml_parser import XMLDocument, XMLPayloadError, parse_xml_document, xml_text

ATOM = "http://www.w3.org/2005/Atom"
CAP = "urn:oasis:names:tc:emergency:cap:1.2"
FMI_SENDER = "urn:oid:2.49.0.0.246.0"
PROFILE = "profile:cap:https://alerts.fmi.fi/cap/profile/"
COLORS = {"Minor": "green", "Moderate": "yellow", "Severe": "orange", "Extreme": "red"}
WARNING_LEVELS = ("none", "green", "yellow", "orange", "red", "unclassified")
BOUNDARY_TOLERANCE = 1e-9


class WarningPayloadError(XMLPayloadError):
    """Classify incomplete CAP without exposing its external text."""

    def __init__(self, message: str, *, reason: str = "invalid_snapshot") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class FMIWarning:
    """A localized location-matched warning without retained source geometry."""

    identifier: str
    event_code: str
    event: str
    severity: str
    color: str | None
    urgency: str
    certainty: str
    sent: datetime
    onset: datetime
    expires: datetime
    headline: str
    description: str
    instruction: str | None
    typical_impacts: str | None
    areas: tuple[str, ...]
    language: str
    web: str | None

    def as_attributes(self) -> dict[str, Any]:
        """Return detached public values rather than integration-owned identity."""
        result = asdict(self)
        result["id"] = result.pop("identifier")
        for key in ("sent", "onset", "expires"):
            result[key] = result[key].isoformat()
        result["areas"] = list(self.areas)
        return result


@dataclass(frozen=True, slots=True)
class WarningSnapshot:
    """One fully checked publication, including applicable future messages."""

    updated: datetime
    warnings: tuple[FMIWarning, ...]


@dataclass(frozen=True, slots=True)
class _Envelope:
    identifier: str
    sender: str
    sent: datetime
    message_type: str
    references: tuple[tuple[str, str, datetime], ...]
    body: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        """Return sender-scoped opaque identity."""
        return self.sender, self.identifier


def _key(namespace: str, name: str) -> str:
    return f"{namespace}}}{name}"


def _text(node: dict[str, Any], name: str, namespace: str = CAP) -> str | None:
    value = xml_text(node.get(_key(namespace, name)))
    return value.strip() if value and value.strip() else None


def _required(node: dict[str, Any], name: str, namespace: str = CAP) -> str:
    value = _text(node, name, namespace)
    if value is None:
        raise WarningPayloadError("missing warning field")
    return value


def _nodes(node: dict[str, Any], name: str, namespace: str = CAP) -> list[dict[str, Any]]:
    value = node.get(_key(namespace, name), [])
    values = value if isinstance(value, list) else [value]
    if any(not isinstance(item, dict) for item in values):
        raise WarningPayloadError("invalid warning elements")
    return values


def _polygons(area: dict[str, Any]) -> list[Any]:
    value = area.get(_key(CAP, "polygon"), [])
    return value if isinstance(value, list) else [value]


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise WarningPayloadError("invalid warning timestamp") from error


def _coordinates(value: str) -> tuple[Point, ...]:
    """Parse finite latitude/longitude pairs without interpreting ring structure."""
    try:
        pairs = [tuple(float(number) for number in pair.split(",")) for pair in value.split()]
    except ValueError as error:
        raise WarningPayloadError("invalid warning polygon") from error
    if any(len(pair) != 2 or not all(map(math.isfinite, pair)) for pair in pairs):
        raise WarningPayloadError("invalid warning polygon")
    return tuple((pair[0], pair[1]) for pair in pairs)


type _Box = tuple[float, float, float, float]


def _box(points: tuple[Point, ...]) -> _Box:
    return (
        min(p[0] for p in points),
        max(p[0] for p in points),
        min(p[1] for p in points),
        max(p[1] for p in points),
    )


def _box_contains(box: _Box, latitude: float, longitude: float) -> bool:
    """Return whether the target lies in the tolerance-expanded vertex bounding box."""
    return (
        box[0] - BOUNDARY_TOLERANCE <= latitude <= box[1] + BOUNDARY_TOLERANCE
        and box[2] - BOUNDARY_TOLERANCE <= longitude <= box[3] + BOUNDARY_TOLERANCE
    )


def _polygon(value: str) -> tuple[Point, ...]:
    points = _coordinates(value)
    if (
        len(points) < 4
        or points[0] != points[-1]
        or len(set(points)) < 3
        or any(not -90 <= lat <= 90 or not -180 <= lon <= 180 for lat, lon in points)
        or any(
            abs(first[1] - second[1]) > 180
            for first, second in zip(points, points[1:], strict=False)
        )
    ):
        raise WarningPayloadError("invalid warning polygon")
    try:
        return validate_ring(points)
    except WarningGeometryError as error:
        raise WarningPayloadError("invalid warning polygon", reason=error.reason) from error


@dataclass(slots=True)
class _GeometryCache:
    """Parse each distinct polygon text once per publication, across languages and messages."""

    boxes: dict[str, _Box] = field(default_factory=dict)
    rings: dict[str, tuple[Point, ...]] = field(default_factory=dict)

    def box(self, text: str) -> _Box:
        """Return a finite vertex bounding box without validating ring structure."""
        if text not in self.boxes:
            points = _coordinates(text)
            if not points:
                raise WarningPayloadError("invalid warning polygon")
            self.boxes[text] = _box(points)
        return self.boxes[text]

    def ring(self, text: str) -> tuple[Point, ...]:
        """Return one validated simple ring."""
        if text not in self.rings:
            self.rings[text] = _polygon(text)
        return self.rings[text]


def polygon_contains(points: tuple[Point, ...], latitude: float, longitude: float) -> bool:
    """Test CAP ring membership with inclusive edges and an independent bbox rejection."""
    if not _box_contains(_box(points), latitude, longitude):
        return False
    inside = False
    for (y1, x1), (y2, x2) in zip(points, points[1:], strict=False):
        length = math.hypot(x2 - x1, y2 - y1)
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if (
            abs(cross) <= BOUNDARY_TOLERANCE * length
            and min(x1, x2) - BOUNDARY_TOLERANCE <= longitude <= max(x1, x2) + BOUNDARY_TOLERANCE
            and min(y1, y2) - BOUNDARY_TOLERANCE <= latitude <= max(y1, y2) + BOUNDARY_TOLERANCE
        ):
            return True
        if (y1 > latitude) != (y2 > latitude) and (
            longitude < x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
        ):
            inside = not inside
    return inside


def _remote(
    body: dict[str, Any], latitude: float, longitude: float, geometry: _GeometryCache
) -> bool:
    """Return whether no ring defined by any source polygon can contain the target."""
    try:
        blocks = _nodes(body, "info")
        for block in blocks:
            areas = _nodes(block, "area")
            if not areas:
                return False
            for area in areas:
                polygons = _polygons(area)
                if not polygons or _key(CAP, "circle") in area:
                    return False
                for value in polygons:
                    if _box_contains(geometry.box(xml_text(value) or ""), latitude, longitude):
                        return False
        return bool(blocks)
    except WarningPayloadError:
        return False


def _areas(
    info: dict[str, Any], latitude: float, longitude: float, geometry: _GeometryCache
) -> tuple[str, ...]:
    areas = _nodes(info, "area")
    if not areas:
        raise WarningPayloadError("missing warning geometry")
    matched: set[str] = set()
    for area in areas:
        name = _required(area, "areaDesc")
        polygons = _polygons(area)
        if not polygons or _key(CAP, "circle") in area:
            raise WarningPayloadError("unsupported warning geometry")
        for value in polygons:
            text = xml_text(value)
            if not text:
                raise WarningPayloadError("invalid warning geometry")
            if polygon_contains(geometry.ring(text), latitude, longitude):
                matched.add(name)
    return tuple(sorted(matched))


def _web(value: str | None) -> str | None:
    try:
        parsed = urlsplit(value or "")
        if (
            parsed.scheme == "https"
            and parsed.hostname
            in {"www.ilmatieteenlaitos.fi", "en.ilmatieteenlaitos.fi", "sv.ilmatieteenlaitos.fi"}
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
        ):
            return value
    except ValueError:
        pass
    return None


def _localized_warning(
    envelope: _Envelope,
    block: dict[str, Any],
    target: tuple[float, float],
    geometry: _GeometryCache,
) -> FMIWarning:
    onset = _timestamp(_required(block, "onset"))
    expires = _timestamp(_required(block, "expires"))
    if expires <= onset:
        raise WarningPayloadError("invalid warning period")
    severity = _required(block, "severity")
    codes = {
        _required(item, "value")
        for item in _nodes(block, "eventCode")
        if (_text(item, "valueName") or "").startswith(PROFILE)
    }
    if len(codes) != 1:
        raise WarningPayloadError("invalid warning event code")
    impacts = next(
        (
            _text(item, "value")
            for item in _nodes(block, "parameter")
            if _text(item, "valueName") == "typicalImpacts"
        ),
        None,
    )
    return FMIWarning(
        envelope.identifier,
        codes.pop(),
        _required(block, "event"),
        severity,
        COLORS.get(severity),
        _required(block, "urgency"),
        _required(block, "certainty"),
        envelope.sent,
        onset,
        expires,
        _required(block, "headline"),
        _required(block, "description"),
        _text(block, "instruction"),
        impacts,
        _areas(block, *target, geometry),
        _required(block, "language"),
        _web(_text(block, "web")),
    )


def _warning(
    envelope: _Envelope,
    latitude: float,
    longitude: float,
    language: str,
    geometry: _GeometryCache,
) -> FMIWarning | None:
    localized: dict[str, FMIWarning] = {}
    signature = None
    for block in _nodes(envelope.body, "info"):
        base = _required(block, "language").lower().split("-")[0]
        if base not in {"en", "fi", "sv"}:
            continue
        warning = _localized_warning(envelope, block, (latitude, longitude), geometry)
        current_signature = (
            warning.onset,
            warning.expires,
            warning.severity,
            warning.event_code,
            warning.urgency,
            warning.certainty,
            bool(warning.areas),
        )
        if signature is not None and signature != current_signature:
            raise WarningPayloadError("inconsistent warning language blocks")
        signature = current_signature
        if base in localized and localized[base] != warning:
            raise WarningPayloadError("conflicting warning language blocks")
        localized[base] = warning
    for candidate in dict.fromkeys((language, "en", "fi", "sv")):
        if candidate in localized:
            result = localized[candidate]
            return result if result.areas else None
    raise WarningPayloadError("missing warning language")


def _envelope(body: dict[str, Any]) -> _Envelope | None:
    if _required(body, "sender") != FMI_SENDER:
        return None
    if _required(body, "status") != "Actual" or _required(body, "scope") != "Public":
        return None
    message_type = _required(body, "msgType")
    if message_type in {"Ack", "Error"}:
        return None
    if message_type not in {"Alert", "Update", "Cancel"}:
        raise WarningPayloadError("unsupported warning message type")
    references = []
    for value in (_text(body, "references") or "").split():
        parts = value.split(",")
        if len(parts) != 3 or not parts[0] or not parts[1]:
            raise WarningPayloadError("invalid warning reference")
        references.append((parts[0], parts[1], _timestamp(parts[2])))
    if message_type != "Alert" and not references:
        raise WarningPayloadError("missing warning references")
    if message_type == "Alert" and references:
        raise WarningPayloadError("unexpected Alert references")
    return _Envelope(
        _required(body, "identifier"),
        FMI_SENDER,
        _timestamp(_required(body, "sent")),
        message_type,
        tuple(references),
        body,
    )


def _validate_references(envelopes: dict[tuple[str, str], _Envelope]) -> set[tuple[str, str]]:
    suppressed: set[tuple[str, str]] = set()
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for key, envelope in envelopes.items():
        targets = set()
        for sender, identifier, sent in envelope.references:
            target = (sender, identifier)
            suppressed.add(target)
            if target in envelopes:
                if envelopes[target].sent != sent:
                    raise WarningPayloadError("inconsistent warning reference timestamp")
                targets.add(target)
        edges[key] = targets
    degrees = dict.fromkeys(edges, 0)
    for targets in edges.values():
        for target in targets:
            degrees[target] += 1
    ready = deque(key for key, degree in degrees.items() if not degree)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for target in edges[key]:
            degrees[target] -= 1
            if not degrees[target]:
                ready.append(target)
    if visited != len(edges):
        raise WarningPayloadError("cyclic warning references")
    return suppressed


def _envelopes(root: dict[str, Any]) -> dict[tuple[str, str], _Envelope]:
    envelopes: dict[tuple[str, str], _Envelope] = {}
    entries = _nodes(root, "entry", ATOM)
    recognized = False
    for entry in entries:
        contents = _nodes(entry, "content", ATOM)
        if len(contents) != 1:
            raise WarningPayloadError("missing warning content")
        content = contents[0]
        body = content.get(_key(CAP, "alert"))
        if body is None and (text := xml_text(content)):
            document = parse_xml_document(text, maximum=const.WARNING_MAX_PAYLOAD_BYTES)
            body = document.get(_key(CAP, "alert"))
        if not isinstance(body, dict):
            raise WarningPayloadError("invalid warning content")
        recognized = recognized or _text(body, "sender") == FMI_SENDER
        envelope = _envelope(body)
        if envelope is None:
            continue
        if envelope.key in envelopes and envelopes[envelope.key] != envelope:
            raise WarningPayloadError("conflicting warning identifier")
        envelopes[envelope.key] = envelope
    if entries and not recognized:
        raise WarningPayloadError("unrecognized warning feed", reason="unrecognized_feed")
    return envelopes


def warning_document(payload: bytes) -> XMLDocument:
    """Parse one bounded publication so several targets can share the same document."""
    try:
        return parse_xml_document(payload, maximum=const.WARNING_MAX_PAYLOAD_BYTES)
    except XMLPayloadError:
        raise WarningPayloadError("invalid or incomplete warning snapshot") from None


def select_warnings(
    document: XMLDocument, latitude: float, longitude: float, language: str
) -> WarningSnapshot:
    """Validate a complete publication before exposing any location-filtered data."""
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise WarningPayloadError("invalid warning target")
    try:
        root = document.get(_key(ATOM, "feed"))
        if not isinstance(root, dict):
            raise WarningPayloadError("invalid warning feed root")
        updated = _timestamp(_required(root, "updated", ATOM))
        envelopes = _envelopes(root)
        suppressed = _validate_references(envelopes)
        geometry = _GeometryCache()
        warnings = tuple(
            warning
            for key, envelope in envelopes.items()
            if key not in suppressed
            and envelope.message_type != "Cancel"
            and not _remote(envelope.body, latitude, longitude, geometry)
            if (warning := _warning(envelope, latitude, longitude, language, geometry)) is not None
        )
        return WarningSnapshot(updated, warnings)
    except XMLPayloadError as error:
        reason = error.reason if isinstance(error, WarningPayloadError) else "invalid_snapshot"
        raise WarningPayloadError("invalid or incomplete warning snapshot", reason=reason) from None


def parse_warning_feed(
    payload: bytes, latitude: float, longitude: float, language: str
) -> WarningSnapshot:
    """Parse and select one publication for one configured target."""
    return select_warnings(warning_document(payload), latitude, longitude, language)
