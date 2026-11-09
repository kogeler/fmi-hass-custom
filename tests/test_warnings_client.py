# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline CAP snapshot, locale, and spatial-selection regressions."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.fmi import const
from custom_components.fmi.warnings_client import WarningPayloadError, parse_warning_feed
from tests.helpers.warnings import POLYGON, SENDER, UPDATED, alert, feed, info


@pytest.mark.parametrize("language,locale", [("fi", "fi-FI"), ("sv", "sv-FI"), ("en", "en-GB")])
@pytest.mark.parametrize("escaped", [False, True])
def test_warning_language_selection_is_coherent(language: str, locale: str, escaped: bool) -> None:
    """Select complete original text independent of XML language ordering."""
    payload = feed(alert(infos=info("sv-FI") + info("en-GB") + info("fi-FI")), escaped=escaped)
    snapshot = parse_warning_feed(payload, 60.5, 24.5, language)
    assert snapshot.updated == datetime(2026, 11, 7, 10, tzinfo=UTC)
    warning = snapshot.warnings[0]
    assert warning.language == locale
    assert warning.headline == f"Invented headline {locale}"
    assert warning.description == f"Invented description {locale}"
    assert warning.color == "orange"
    assert warning.instruction is None
    assert warning.areas == (f"Invented area {locale}",)


def test_warning_missing_locale_falls_back_without_discarding_new_event() -> None:
    """Unknown event codes remain visible and carry their actual fallback language."""
    snapshot = parse_warning_feed(
        feed(alert(infos=info(event_code="futureEvent"))), 60.5, 24.5, "fi"
    )
    assert snapshot.warnings[0].event_code == "futureEvent"
    assert snapshot.warnings[0].language == "en-GB"


@pytest.mark.parametrize("latitude,longitude", [(60.5, 24.5), (60, 24.5), (60, 24), (61, 25)])
def test_warning_geometry_includes_edges_and_vertices(latitude: float, longitude: float) -> None:
    assert len(parse_warning_feed(feed(alert()), latitude, longitude, "en").warnings) == 1


def test_warning_geometry_filters_point_and_unions_areas_without_double_counting() -> None:
    duplicated_area = info().replace(
        "</info>", f"<area><areaDesc>Second</areaDesc><polygon>{POLYGON}</polygon></area></info>"
    )
    payload = feed(alert(infos=duplicated_area))
    assert len(parse_warning_feed(payload, 60.5, 24.5, "en").warnings) == 1
    assert parse_warning_feed(payload, 62, 24.5, "en").warnings == ()
    concave = "60,24 62,24 62,25 61,25 61,26 60,26 60,24"
    snapshot = parse_warning_feed(feed(alert(infos=info(polygon=concave))), 61.5, 25.5, "en")
    assert snapshot.warnings == ()


@pytest.mark.parametrize("message_type", ["Update", "Cancel"])
@pytest.mark.parametrize("reverse", [False, True])
def test_warning_references_apply_before_filtering_and_ignore_document_order(
    message_type: str, reverse: bool
) -> None:
    old = alert("old")
    replacement = alert(
        "new",
        message_type=message_type,
        references=f"{SENDER},old,{UPDATED}",
        infos="" if message_type == "Cancel" else info(),
    )
    items = (replacement, old) if reverse else (old, replacement)
    result = parse_warning_feed(feed(*items), 60.5, 24.5, "en")
    expected = [] if message_type == "Cancel" else ["new"]
    assert [item.identifier for item in result.warnings] == expected


def test_warning_snapshot_does_not_require_history_or_an_explicit_cancel() -> None:
    replacement = alert("new", message_type="Update", references=f"{SENDER},missing,{UPDATED}")
    assert len(parse_warning_feed(feed(replacement), 60.5, 24.5, "en").warnings) == 1
    assert parse_warning_feed(feed(), 60.5, 24.5, "en").warnings == ()
    assert parse_warning_feed(feed(alert(status="Test")), 60.5, 24.5, "en").warnings == ()


@pytest.mark.parametrize(
    "payload",
    [
        feed(alert(infos=info(polygon="60,24 61,24 61,25"))),
        feed(alert(infos=info(polygon="nan,24 61,24 61,25 nan,24"))),
        feed(alert(infos=info(onset="2026-11-07T09:00:00"))),
        feed(alert(infos=info(expires="2026-11-07T08:00:00Z"))),
        feed(alert(infos=info("en-GB") + info("fi-FI", severity="Extreme"))),
        feed(alert("same"), alert("same", infos=info(severity="Extreme"))),
        feed(
            alert("a", message_type="Update", references=f"{SENDER},b,{UPDATED}"),
            alert("b", message_type="Update", references=f"{SENDER},a,{UPDATED}"),
        ),
        b'<feed xmlns="urn:wrong"><updated>2026-11-07T10:00:00Z</updated></feed>',
    ],
)
def test_incomplete_warning_snapshots_never_become_an_all_clear(payload: bytes) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(payload, 60.5, 24.5, "en")


def test_warning_duplicate_republication_and_unknown_severity_remain_visible() -> None:
    item = alert(infos=info(severity="FutureSeverity"))
    snapshot = parse_warning_feed(feed(item, item), 60.5, 24.5, "en")
    assert len(snapshot.warnings) == 1
    assert snapshot.warnings[0].color is None


@pytest.mark.parametrize(
    "polygon,latitude,longitude",
    [
        ("60,24 61,24 60,24 60,24", 60.5, 24),
        ("60,24,1 61,24,1 61,25,1 60,24,1", 60.5, 24.5),
        ("91,24 61,24 61,25 91,24", 62, 24.5),
        ("60,181 61,24 61,25 60,181", 60.5, 24.5),
        ("60,170 61,-170 61,170 60,170", 60.5, 24.5),
        ("not-a-number,24 61,24 61,25 not-a-number,24", 60.5, 24.5),
    ],
)
def test_warning_invalid_rings_cannot_establish_absence(
    polygon: str, latitude: float, longitude: float
) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert(infos=info(polygon=polygon))), latitude, longitude, "en")


def test_warning_repeated_vertices_and_longitude_bbox_are_deterministic() -> None:
    polygon = "60,24 60,24 61,24 61,25 60,25 60,24"
    payload = feed(alert(infos=info(polygon=polygon)))
    assert len(parse_warning_feed(payload, 60.5, 24.5, "en").warnings) == 1
    assert parse_warning_feed(payload, 60.5, 26, "en").warnings == ()


@pytest.mark.parametrize(
    "body",
    [
        "<info/>",
        info().replace("<headline>Invented headline en-GB</headline>", "<headline> </headline>"),
        info().split("<area>")[0] + "</info>",
        info().replace(f"<polygon>{POLYGON}</polygon>", ""),
        info().replace(f"<polygon>{POLYGON}</polygon>", "<polygon/>"),
        info().replace("</area>", "<circle>60,24 10</circle></area>"),
        info().replace("profile:cap:https://alerts.fmi.fi/cap/profile/", "unrelated-profile:"),
        info("de-DE"),
        info() + info().replace("Invented headline", "Conflicting headline"),
    ],
)
def test_warning_malformed_mandatory_and_conflicting_fields_fail_snapshot(body: str) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert(infos=body)), 60.5, 24.5, "en")


@pytest.mark.parametrize(
    "payload",
    [
        feed().replace(b"</feed>", b"<entry>broken</entry></feed>"),
        feed().replace(b"</feed>", b"<entry><title>No CAP</title></entry></feed>"),
        feed().replace(b"</feed>", b"<entry><content><other/></content></entry></feed>"),
        feed().replace(b"</feed>", b"<entry><content>not XML</content></entry></feed>"),
        feed().replace(b"</feed>", b"<entry><content/><content/></entry></feed>"),
        feed().replace(b"<updated>", b"<missing>"),
    ],
)
def test_warning_invalid_atom_containers_are_classified(payload: bytes) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(payload, 60.5, 24.5, "en")


@pytest.mark.parametrize(
    "latitude,longitude", [(float("nan"), 24), (60, float("inf")), (91, 24), (60, 181)]
)
def test_warning_target_must_be_finite_wgs84(latitude: float, longitude: float) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(), latitude, longitude, "en")


@pytest.mark.parametrize(
    "replacement",
    [
        {"message_type": "FutureType"},
        {"message_type": "Update"},
        {"message_type": "Cancel", "references": "broken"},
        {"message_type": "Update", "references": f",old,{UPDATED}"},
        {"message_type": "Update", "references": f"{SENDER},,{UPDATED}"},
    ],
)
def test_warning_invalid_message_control_is_not_silently_ignored(replacement) -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert(**replacement)), 60.5, 24.5, "en")


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            feed(alert(), alert("other").replace(SENDER, "urn:example:another-authority")),
            ["synthetic-one"],
        ),
        (feed(alert().replace("<scope>Public</scope>", "<scope>Restricted</scope>")), []),
        (feed(alert(message_type="Ack")), []),
        (feed(alert(message_type="Error")), []),
    ],
)
def test_warning_non_operational_or_other_authority_messages_are_not_fmi(
    payload: bytes, expected: list[str]
) -> None:
    warnings = parse_warning_feed(payload, 60.5, 24.5, "en").warnings
    assert [warning.identifier for warning in warnings] == expected


def test_warning_feed_without_an_fmi_envelope_is_not_an_all_clear() -> None:
    other = feed(alert().replace(SENDER, "urn:example:another-authority"))
    with pytest.raises(WarningPayloadError) as raised:
        parse_warning_feed(other, 60.5, 24.5, "en")
    assert raised.value.reason == "unrecognized_feed"
    assert parse_warning_feed(feed(alert(status="Test")), 60.5, 24.5, "en").warnings == ()


def test_warning_reference_graph_supports_split_and_chained_replacements() -> None:
    parent = alert("parent")
    reference = f"{SENDER},parent,{UPDATED}"
    first = alert("first", message_type="Update", references=reference)
    second = alert("second", message_type="Update", references=reference)
    snapshot = parse_warning_feed(feed(parent, first, second), 60.5, 24.5, "en")
    assert {warning.identifier for warning in snapshot.warnings} == {"first", "second"}
    bad = alert("bad", message_type="Update", references=f"{SENDER},parent,2026-11-07T09:00:00Z")
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(parent, bad), 60.5, 24.5, "en")


@pytest.mark.parametrize("locale", ["fi-FI", "sv-FI"])
def test_warning_fallback_exhausts_supported_original_languages(locale: str) -> None:
    block = info(locale) + info("de-DE")
    snapshot = parse_warning_feed(feed(alert(infos=block)), 60.5, 24.5, "en")
    assert snapshot.warnings[0].language == locale


@pytest.mark.parametrize(
    "url",
    [
        "http://en.ilmatieteenlaitos.fi/warnings",
        "https://example.invalid/",
        "https://user@en.ilmatieteenlaitos.fi/",
        "https://user:password@en.ilmatieteenlaitos.fi/",
        "https://en.ilmatieteenlaitos.fi:123/",
        "https://en.ilmatieteenlaitos.fi:bad/",
        "https://[invalid/",
    ],
)
def test_warning_web_links_are_inert_when_not_official_https(url: str) -> None:
    block = info().replace("https://en.ilmatieteenlaitos.fi/warnings", url)
    assert parse_warning_feed(feed(alert(infos=block)), 60.5, 24.5, "en").warnings[0].web is None


def test_warning_optional_instructions_and_impacts_preserve_official_text() -> None:
    block = info().replace(
        "</info>",
        """
        <instruction>Invented official instruction</instruction>
        <parameter><valueName>unrelated</valueName><value>Ignore</value></parameter>
        <parameter><valueName>typicalImpacts</valueName><value>Invented impacts</value></parameter>
        </info>""",
    )
    warning = parse_warning_feed(feed(alert(infos=block)), 60.5, 24.5, "en").warnings[0]
    assert warning.instruction == "Invented official instruction"
    assert warning.typical_impacts == "Invented impacts"


def test_warning_supported_size_limit_remains_a_classified_failure() -> None:
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(b" " * (const.WARNING_MAX_PAYLOAD_BYTES + 1), 60.5, 24.5, "en")


def test_alert_references_cannot_suppress_an_active_warning() -> None:
    invalid = alert(
        "outside",
        references=f"{SENDER},active,{UPDATED}",
        infos=info(polygon="62,24 63,24 63,25 62,25 62,24"),
    )
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert("active"), invalid), 60.5, 24.5, "en")


@pytest.mark.parametrize("field,value", [("certainty", "Possible"), ("urgency", "Future")])
def test_warning_language_classifications_must_agree(field, value) -> None:
    old = "Likely" if field == "certainty" else "Immediate"
    other = info("sv-FI").replace(f"<{field}>{old}</{field}>", f"<{field}>{value}</{field}>")
    for language in ("en", "sv"):
        with pytest.raises(WarningPayloadError):
            parse_warning_feed(feed(alert(infos=info() + other)), 60.5, 24.5, language)


@pytest.mark.parametrize(
    "ring",
    [
        "60,24 60,25 60,26 60,24",
        "60,24 62,26 60,26 61,24 60,24",
        "60,24 61,24 61,25 60,24 60,25 60,24",
        "60,24 60,26 60,25 61,25 61,24 60,24",
        "60,24 60,28 62,28 62,25 60,25 60,27 61,27 61,24 60,24",
    ],
)
def test_warning_non_simple_geometry_fails_before_location_filtering(ring) -> None:
    latitude, longitude = map(float, ring.split()[0].split(","))
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert(infos=info(polygon=ring))), latitude, longitude, "en")
    remote = parse_warning_feed(feed(alert(infos=info(polygon=ring))), 65, 29, "en")
    assert remote.warnings == ()


def test_warning_geometry_complexity_is_bounded(monkeypatch) -> None:
    from custom_components.fmi import warning_geometry

    monkeypatch.setattr(warning_geometry, "MAX_GEOMETRY_COMPARISONS", 0)
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert()), 60.5, 24.5, "en")


def test_warning_parallel_diagonal_edges_remain_a_valid_ring() -> None:
    block = info(polygon="60,24 63,27 63,28 60,25 60,24")
    assert parse_warning_feed(feed(alert(infos=block)), 61, 25.5, "en").warnings


def test_warning_large_valid_ring_and_exact_xml_boundary() -> None:
    vertices = [
        (60.5 + 0.4 * math.cos(i * math.tau / 2000), 24.5 + 0.4 * math.sin(i * math.tau / 2000))
        for i in range(2000)
    ]
    polygon = " ".join(f"{a:.10f},{b:.10f}" for a, b in [*vertices, vertices[0]])
    payload = feed(alert(infos=info(polygon=polygon)))
    maximum = const.WARNING_MAX_PAYLOAD_BYTES
    payload = payload.replace(
        b"</feed>", b"<!--" + b"x" * (maximum - len(payload) - 7) + b"--></feed>"
    )
    assert len(payload) == maximum
    assert len(parse_warning_feed(payload, 60.5, 24.5, "en").warnings) == 1
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(payload + b" ", 60.5, 24.5, "en")


@pytest.mark.parametrize("latitude,expected", [(60 - 0.5e-9, True), (60 - 2e-9, False)])
def test_warning_numerical_tolerance_is_not_a_search_radius(latitude, expected) -> None:
    assert bool(parse_warning_feed(feed(alert()), latitude, 24.5, "en").warnings) is expected


@pytest.mark.parametrize("offset", ["+02:00", "+03:00"])
def test_warning_offsets_normalize_across_utc_date_boundary(offset) -> None:
    block = info(onset=f"2026-11-07T00:00:00{offset}", expires=f"2026-11-07T01:00:00{offset}")
    warning = parse_warning_feed(feed(alert(infos=block)), 60.5, 24.5, "en").warnings[0]
    assert warning.onset.day == 6
    assert warning.onset.hour == (22 if offset == "+02:00" else 21)
    assert warning.expires - warning.onset == timedelta(hours=1)


@pytest.mark.parametrize(
    "severity,color",
    [("Minor", "green"), ("Moderate", "yellow"), ("Severe", "orange"), ("Extreme", "red")],
)
def test_warning_all_official_severity_colors(severity, color) -> None:
    warning = parse_warning_feed(
        feed(alert(infos=info(severity=severity))), 60.5, 24.5, "en"
    ).warnings[0]
    assert warning.color == color


FAR = "70,20 71,20 71,21 70,21 70,20"


@pytest.mark.parametrize(
    "remote",
    [
        info(polygon="70,24 70,25 70,26 70,24"),
        info(polygon="70,24 72,26 70,26 71,24 70,24"),
        info(polygon="91,24 71,24 71,25 91,24"),
        info(polygon="70,24 71,24 71,25"),
        info(polygon="70,170 71,-170 71,170 70,170"),
        info(polygon=FAR).replace("<headline>Invented headline en-GB</headline>", ""),
        info(polygon=FAR) + info("fi-FI", polygon=FAR, severity="Extreme"),
        info(polygon=FAR, onset="2026-11-07T09:00:00"),
    ],
)
def test_warning_remote_defects_cannot_hide_a_local_warning(remote: str) -> None:
    """A message whose every polygon bbox excludes the target cannot change its result."""
    payload = feed(alert("local"), alert("remote", infos=remote))
    snapshot = parse_warning_feed(payload, 60.5, 24.5, "en")
    assert [warning.identifier for warning in snapshot.warnings] == ["local"]


@pytest.mark.parametrize(
    "unresolved",
    [
        "",
        "<info>text</info>",
        info(polygon=FAR).replace("</area>", "<circle>70,20 10</circle></area>"),
        info(polygon="70,20 71,x 71,21 70,20"),
        info(polygon=FAR).replace(f"<polygon>{FAR}</polygon>", "<polygon/>"),
        info(polygon=FAR).replace(f"<polygon>{FAR}</polygon>", ""),
        info(polygon=FAR) + info("fi-FI").split("<area>")[0] + "</info>",
    ],
)
def test_warning_geometry_that_cannot_be_bounded_still_fails(unresolved: str) -> None:
    """Remoteness needs finite polygons for every block; otherwise the snapshot fails."""
    with pytest.raises(WarningPayloadError):
        parse_warning_feed(feed(alert("local"), alert("x", infos=unresolved)), 60.5, 24.5, "en")


def test_warning_far_polygon_in_a_matching_message_is_rejected_by_bbox() -> None:
    """A union can mix a containing polygon with a far one without changing the match."""
    block = info().replace(
        "</info>", f"<area><areaDesc>Far</areaDesc><polygon>{FAR}</polygon></area></info>"
    )
    warning = parse_warning_feed(feed(alert(infos=block)), 60.5, 24.5, "en").warnings[0]
    assert warning.areas == ("Invented area en-GB",)


def _comb(teeth: int, width: float = 0.001) -> str:
    vertices = [(60.0, 24.0)]
    for tooth in range(teeth):
        left, right = 24 + 2 * tooth * width, 24 + (2 * tooth + 1) * width
        vertices += [(61.0, left), (61.0, right), (60.1, right), (60.1, right + width)]
    vertices += [(60.0, vertices[-1][1]), (60.0, 24.0)]
    return " ".join(f"{latitude:.6f},{longitude:.6f}" for latitude, longitude in vertices)


def test_warning_dense_valid_ring_uses_the_cheaper_sweep_axis() -> None:
    """A long east-west comb is valid although a latitude-only sweep exceeds the budget."""
    from custom_components.fmi import warning_geometry
    from custom_components.fmi.warnings_client import _coordinates

    polygon = _comb(500)
    segments = warning_geometry._segments(_coordinates(polygon))
    latitude_cost = warning_geometry._sweep_candidates(segments, 0)
    longitude_cost = warning_geometry._sweep_candidates(segments, 1)
    assert latitude_cost > warning_geometry.MAX_GEOMETRY_COMPARISONS > 100 * longitude_cost
    snapshot = parse_warning_feed(feed(alert(infos=info(polygon=polygon))), 60.5, 24.0005, "en")
    assert len(snapshot.warnings) == 1
    assert parse_warning_feed(feed(alert(infos=info(polygon=polygon))), 60.05, 24.5, "en").warnings


@pytest.mark.parametrize("ring", [POLYGON, "60,24 62,24 62,25 61,25 61,26 60,26 60,24", _comb(4)])
def test_warning_sweep_cost_matches_an_exhaustive_count(ring: str) -> None:
    from custom_components.fmi import warning_geometry
    from custom_components.fmi.warnings_client import _coordinates

    segments = warning_geometry._segments(_coordinates(ring))
    for axis in (0, 1):
        ordered = sorted(segments, key=lambda item: item.bounds[2 * axis])
        exhaustive = sum(
            ordered[earlier].bounds[2 * axis + 1] >= ordered[later].bounds[2 * axis]
            for later in range(len(ordered))
            for earlier in range(later)
        )
        assert warning_geometry._sweep_candidates(segments, axis) == exhaustive


def test_warning_geometry_budget_reports_its_reason(monkeypatch) -> None:
    from custom_components.fmi import warning_geometry

    monkeypatch.setattr(warning_geometry, "MAX_GEOMETRY_COMPARISONS", 0)
    with pytest.raises(WarningPayloadError) as raised:
        parse_warning_feed(feed(alert()), 60.5, 24.5, "en")
    assert raised.value.reason == "geometry_too_complex"


def test_warning_document_is_parsed_once_for_several_targets() -> None:
    from custom_components.fmi.warnings_client import select_warnings, warning_document

    document = warning_document(feed(alert()))
    assert len(select_warnings(document, 60.5, 24.5, "en").warnings) == 1
    assert select_warnings(document, 65, 29, "en").warnings == ()
    with pytest.raises(WarningPayloadError) as raised:
        warning_document(b"<broken>")
    assert raised.value.reason == "invalid_snapshot"


def test_warning_feed_ceiling_is_separate_from_the_shared_xml_limit() -> None:
    """Storm-sized CAP feeds use their own ceiling; other FMI XML keeps the shared bound."""
    from custom_components.fmi.xml_parser import XMLPayloadError, parse_xml_document

    filler = b"<!--" + b"x" * const.XML_MAX_PAYLOAD_BYTES + b"--></feed>"
    payload = feed(alert()).replace(b"</feed>", filler)
    assert const.XML_MAX_PAYLOAD_BYTES < len(payload) < const.WARNING_MAX_PAYLOAD_BYTES
    assert len(parse_warning_feed(payload, 60.5, 24.5, "en").warnings) == 1
    with pytest.raises(XMLPayloadError):
        parse_xml_document(payload)


def _storm_feed(messages: int, vertices: int) -> bytes:
    """Invent a publication shaped like FMI's: one ring repeated in three language blocks."""
    alerts = []
    for index in range(messages):
        covering = index % 2 == 0
        lat = 60.5 + (index * 1e-4 if covering else 2 + index % 7)
        lon = 24.5 + (index * 1e-4 if covering else index % 5)
        angles = [i * math.tau / vertices for i in range(vertices)]
        ring = [(lat + 0.4 * math.cos(a), lon + 0.4 * math.sin(a)) for a in angles]
        polygon = " ".join(f"{a:.6f},{b:.6f}" for a, b in [*ring, ring[0]])
        blocks = "".join(info(locale, polygon=polygon) for locale in ("fi-FI", "sv-FI", "en-GB"))
        alerts.append(alert(f"storm-{index}", infos=blocks))
    return feed(*alerts)


def test_warning_storm_sized_publication_stays_within_bounded_resources() -> None:
    """Near-ceiling feeds parse with bounded transient memory; half the rings cover the target."""
    import tracemalloc

    payload = _storm_feed(64, 4000)
    assert const.XML_MAX_PAYLOAD_BYTES * 6 < len(payload) < const.WARNING_MAX_PAYLOAD_BYTES
    tracemalloc.start()
    try:
        snapshot = parse_warning_feed(payload, 60.5, 24.5, "en")
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert sorted(int(item.identifier.split("-")[1]) for item in snapshot.warnings) == list(
        range(0, 64, 2)
    )
    assert peak < 4 * len(payload)
