# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Prove the independent live recognition assertion detects silent parser loss."""

from dataclasses import replace

import pytest

from tests.helpers import warning_live
from tests.helpers.warnings import POLYGON, SENDER, UPDATED, alert, feed, info

EMPTY_POLYGON = '<polygon kind="x"/>'


@pytest.mark.parametrize("escaped", [True, False])
def test_warning_live_recognition_checks_source_identity_and_allows_language_fallback(escaped):
    result = warning_live.validate_live_warning_recognition(
        feed(alert("one", infos=info("en-GB")), alert("two", infos=info("sv-FI")), escaped=escaped),
        "fi",
    )
    assert result["operational"] == result["boundary_checked"] == 2
    assert warning_live.validate_live_warning_recognition(feed(), "en")["entries"] == 0


def test_warning_live_recognition_rejects_silent_parser_loss(monkeypatch):
    select = warning_live.select_warnings
    monkeypatch.setattr(
        warning_live, "select_warnings", lambda *args: replace(select(*args), warnings=())
    )
    with pytest.raises(AssertionError, match="lost a source warning"):
        warning_live.validate_live_warning_recognition(feed(alert()), "en")


def test_warning_live_recognition_rejects_incoherent_language(monkeypatch):
    select = warning_live.select_warnings
    monkeypatch.setattr(
        warning_live, "select_warnings", lambda doc, lat, lon, _: select(doc, lat, lon, "en")
    )
    with pytest.raises(AssertionError, match="coherent fallback"):
        warning_live.validate_live_warning_recognition(
            feed(alert(infos=info("en-GB") + info("fi-FI"))), "fi"
        )


def test_warning_live_recognition_distinguishes_cancellations_and_unknown_authority():
    payload = feed(
        alert("old"),
        alert("cancel", message_type="Cancel", infos="", references=f"{SENDER},old,{UPDATED}"),
        alert("ack", message_type="Ack", infos=""),
    )
    result = warning_live.validate_live_warning_recognition(payload, "en")
    assert result["operational"] == 3 and result["boundary_checked"] == 0
    with pytest.raises(AssertionError, match="no recognized operational sender"):
        warning_live.validate_live_warning_recognition(feed(alert(status="Test")), "en")


@pytest.mark.parametrize(
    "payload,message",
    [
        (feed().replace(b"</feed>", b"<entry><title>x</title></entry></feed>"), "no content"),
        (
            feed().replace(b"</feed>", b"<entry><content>&lt;x/&gt;</content></entry></feed>"),
            "no CAP alert",
        ),
        (feed(alert().replace("<identifier>synthetic-one</identifier>", "")), "no identifier"),
        (feed(alert(infos="")), "no info"),
        (feed(alert(infos=info().split("<area>")[0] + "</info>")), "no area"),
        (feed(alert(infos=info(polygon="").replace("<polygon></polygon>", ""))), "no polygon"),
        (
            feed(alert(infos=info().replace(f"<polygon>{POLYGON}</polygon>", EMPTY_POLYGON))),
            "empty polygon",
        ),
    ],
)
def test_warning_live_recognition_classifies_missing_source_elements(payload, message):
    with pytest.raises(AssertionError, match=message):
        warning_live.validate_live_warning_recognition(payload, "en")


def test_warning_live_structure_summary_contains_only_counts(tmp_path):
    structure = {"entries": 2, "operational": 2, "boundary_checked": 1, "bytes": 512}
    warning_live.record_live_structure(tmp_path, "sv", structure)
    assert (tmp_path / "cap-sv.txt").read_text(encoding="ascii") == (
        "FMI CAP sv: entries=2 operational=2 boundary_checked=1 bytes=512\n"
    )
