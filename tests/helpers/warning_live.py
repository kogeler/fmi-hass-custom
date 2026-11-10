# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Independent source-identity and public-boundary checks without extra network calls."""

from pathlib import Path
from typing import Any

from custom_components.fmi.warnings_client import select_warnings, warning_document
from custom_components.fmi.xml_parser import parse_xml_document, xml_text

ATOM = "http://www.w3.org/2005/Atom}"
CAP = "urn:oasis:names:tc:emergency:cap:1.2}"
FMI_SENDER = "urn:oid:2.49.0.0.246.0"
SUPPORTED = ("en", "fi", "sv")
NOT_WARNINGS = frozenset({"Cancel", "Ack", "Error"})


def _many(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _child(node: Any, name: str, context: str) -> Any:
    value = node.get(CAP + name) if isinstance(node, dict) else None
    assert value not in (None, [], ""), f"FMI CAP {context} has no {name}"
    return value


def _alert(entry: Any) -> dict[str, Any]:
    content = entry.get(ATOM + "content") if isinstance(entry, dict) else None
    assert content is not None, "FMI feed entry has no content"
    body = content.get(CAP + "alert") if isinstance(content, dict) else None
    if body is None:
        body = parse_xml_document(xml_text(content) or "").get(CAP + "alert")
    assert isinstance(body, dict), "FMI feed entry contains no CAP alert"
    return body


def _base(block: Any) -> str:
    return (xml_text(block.get(CAP + "language")) or "").lower().split("-")[0]


def validate_live_warning_recognition(payload: bytes, language: str) -> dict[str, int]:
    """Require every surviving source warning to survive production parsing at its own vertex."""
    document = warning_document(payload)
    root = document.get(ATOM + "feed")
    assert isinstance(root, dict), "FMI CAP publication has no Atom feed root"
    entries = _many(root.get(ATOM + "entry"))
    operational = [
        body
        for body in map(_alert, entries)
        if body.get(CAP + "sender") == FMI_SENDER
        and body.get(CAP + "status") == "Actual"
        and body.get(CAP + "scope") == "Public"
    ]
    assert not entries or operational, "Nonempty FMI feed contains no recognized operational sender"
    suppressed = {
        reference.split(",")[1]
        for body in operational
        for reference in (body.get(CAP + "references") or "").split()
    }
    checked = 0
    for body in operational:
        identity = _child(body, "identifier", "alert")
        if identity in suppressed or _child(body, "msgType", identity) in NOT_WARNINGS:
            continue
        blocks = _many(_child(body, "info", identity))
        area = _many(_child(blocks[0], "area", f"{identity} info"))[0]
        vertex = (xml_text(_many(_child(area, "polygon", f"{identity} area"))[0]) or "").split()
        assert vertex, f"FMI CAP {identity} area has an empty polygon"
        latitude, longitude = map(float, vertex[0].split(","))
        snapshot = select_warnings(document, latitude, longitude, language)
        matches = [item for item in snapshot.warnings if item.identifier == identity]
        assert len(matches) == 1, "Production CAP parser lost a source warning at its own boundary"
        available = {_base(block) for block in blocks}
        expected = next(item for item in (language, *SUPPORTED) if item in available)
        assert matches[0].language.lower().split("-")[0] == expected, (
            "Production CAP text language does not follow the coherent fallback order"
        )
        checked += 1
    return {
        "entries": len(entries),
        "operational": len(operational),
        "boundary_checked": checked,
        "bytes": len(payload),
    }


def record_live_structure(root: Path, language: str, structure: dict[str, int]) -> None:
    """Expose public structural counts for the live target output, never message content."""
    counts = " ".join(f"{key}={value}" for key, value in structure.items())
    (root / f"cap-{language}.txt").write_text(f"FMI CAP {language}: {counts}\n", encoding="ascii")
