# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Bounded XML parsing for data received from FMI."""

from __future__ import annotations

from typing import Any
from xml.parsers import expat

import xmltodict

from .const import XML_MAX_PAYLOAD_BYTES

type XMLDocument = dict[str, Any]
MINIMUM_EXPAT_VERSION = (2, 7, 2)


class XMLPayloadError(ValueError):
    """Report malformed, unsafe, or oversized external XML."""


def ensure_safe_expat() -> None:
    """Reject runtimes below Python's documented safe Expat baseline."""
    if expat.version_info < MINIMUM_EXPAT_VERSION:
        installed = ".".join(str(part) for part in expat.version_info)
        required = ".".join(str(part) for part in MINIMUM_EXPAT_VERSION)
        raise XMLPayloadError(f"Expat {installed} is older than required {required}")


def parse_xml_document(payload: str | bytes) -> XMLDocument:
    """Parse bounded XML without enabling entity expansion or external resources."""
    ensure_safe_expat()
    payload_size = len(payload) if isinstance(payload, bytes) else len(payload.encode("utf-8"))
    if payload_size > XML_MAX_PAYLOAD_BYTES:
        raise XMLPayloadError("XML payload exceeds size limit")

    try:
        document = xmltodict.parse(
            payload,
            disable_entities=True,
            process_namespaces=True,
            namespace_separator="}",
        )
    except (expat.ExpatError, ValueError) as error:
        raise XMLPayloadError("invalid or unsafe XML") from error
    if not isinstance(document, dict):
        raise XMLPayloadError("invalid XML document")
    return document


def xml_local_name(name: str) -> str:
    """Return a namespace-independent XML name."""
    return name.rsplit("}", 1)[-1]


def xml_children(node: object) -> list[tuple[str, object]]:
    """Return element children in document order, expanding repeated elements."""
    if not isinstance(node, dict):
        return []

    children: list[tuple[str, object]] = []
    for name, value in node.items():
        if not isinstance(name, str) or name.startswith(("@", "#")):
            continue
        if isinstance(value, list):
            children.extend((name, item) for item in value)
        else:
            children.append((name, value))
    return children


def iter_xml_elements(node: object, local_name: str):
    """Yield matching element values in document order without recursive traversal."""
    stack = list(reversed(xml_children(node)))
    while stack:
        name, value = stack.pop()
        if xml_local_name(name) == local_name:
            yield value
        stack.extend(reversed(xml_children(value)))


def xml_attribute(node: object, local_name: str) -> str | None:
    """Return a string attribute selected by local name."""
    if not isinstance(node, dict):
        return None
    for name, value in node.items():
        if (
            isinstance(name, str)
            and name.startswith("@")
            and xml_local_name(name[1:]) == local_name
            and isinstance(value, str)
        ):
            return value
    return None


def xml_text(node: object) -> str | None:
    """Return simple element text from an xmltodict value."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text = node.get("#text")
        if isinstance(text, str):
            return text
    return None
