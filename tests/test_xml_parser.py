# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Security and shape contracts for integration-owned FMI XML parsing."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.fmi import xml_parser
from custom_components.fmi.xml_parser import (
    XMLPayloadError,
    ensure_safe_expat,
    iter_xml_elements,
    parse_xml_document,
    xml_attribute,
    xml_children,
    xml_local_name,
    xml_text,
)


def test_namespace_elements_attributes_and_text_retain_document_order() -> None:
    """Decode the small XML subset used by FMI without namespace-prefix coupling."""
    document = parse_xml_document(
        """
        <root xmlns:swe="urn:example">
          <swe:field name="first">one</swe:field>
          <swe:field name="second"><child>two</child></swe:field>
        </root>
        """
    )

    fields = list(iter_xml_elements(document, "field"))
    assert [xml_attribute(field, "name") for field in fields] == ["first", "second"]
    assert xml_text(fields[0]) == "one"
    assert xml_text(next(iter_xml_elements(fields[1], "child"))) == "two"
    assert xml_local_name("urn:example}field") == "field"


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE root [<!ENTITY value "unsafe">]><root>&value;</root>',
        (b'<!DOCTYPE root [<!ENTITY value SYSTEM "file:///etc/passwd">]><root>&value;</root>'),
    ],
)
def test_entity_declarations_are_rejected(payload: bytes) -> None:
    """Keep xmltodict's secure entity setting explicit and regression-tested."""
    with pytest.raises(XMLPayloadError, match="invalid or unsafe XML"):
        parse_xml_document(payload)


def test_external_dtd_is_not_resolved() -> None:
    """Expat has no external-resource handler and leaves an external DTD inert."""
    document = parse_xml_document(
        b'<!DOCTYPE root SYSTEM "file:///etc/passwd"><root>expected</root>'
    )

    assert document == {"root": "expected"}


@pytest.mark.parametrize("payload", [b"", b"<root><broken></root>"])
def test_malformed_or_empty_xml_is_classified(payload: bytes) -> None:
    """Normalize Expat syntax failures at the integration boundary."""
    with pytest.raises(XMLPayloadError, match="invalid or unsafe XML"):
        parse_xml_document(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"x" * (xml_parser.XML_MAX_PAYLOAD_BYTES + 1),
        "ä" * (xml_parser.XML_MAX_PAYLOAD_BYTES // 2 + 1),
    ],
)
def test_xml_payload_byte_size_is_bounded(payload: str | bytes) -> None:
    """Apply the same byte ceiling to byte and text inputs."""
    with pytest.raises(XMLPayloadError, match="exceeds size limit"):
        parse_xml_document(payload)


def test_unexpected_parser_result_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not expose an unvalidated third-party return shape to callers."""
    monkeypatch.setattr(xml_parser.xmltodict, "parse", lambda *args, **kwargs: None)

    with pytest.raises(XMLPayloadError, match="invalid XML document"):
        parse_xml_document("<root />")


def test_unsupported_expat_runtime_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enforce the minimum version documented by current CPython XML guidance."""
    monkeypatch.setattr(xml_parser.expat, "version_info", (2, 7, 1))

    with pytest.raises(XMLPayloadError, match=r"Expat 2\.7\.1.*2\.7\.2"):
        ensure_safe_expat()


def test_helpers_ignore_non_element_shapes() -> None:
    """Ignore attributes, text metadata, and unexpected non-string dictionary keys."""
    node: dict[Any, object] = {
        1: "ignored",
        "@name": "attribute",
        "#text": "value",
        "child": ["one", "two"],
    }

    assert xml_children(node) == [("child", "one"), ("child", "two")]
    assert xml_children("not-a-node") == []
    assert xml_attribute(node, "name") == "attribute"
    assert xml_attribute("not-a-node", "name") is None
    assert xml_attribute({"@name": 1}, "name") is None
    assert xml_text(node) == "value"
    assert xml_text({"#text": 1}) is None
    assert xml_text(None) is None
