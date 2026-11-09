# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Small invented CAP publications for offline warning regressions."""

from xml.sax.saxutils import escape

CAP = "urn:oasis:names:tc:emergency:cap:1.2"
ATOM = "http://www.w3.org/2005/Atom"
SENDER = "urn:oid:2.49.0.0.246.0"
UPDATED = "2026-11-07T10:00:00Z"
POLYGON = "60,24 61,24 61,25 60,25 60,24"


def info(
    language: str = "en-GB",
    *,
    polygon: str = POLYGON,
    onset: str = "2026-11-07T09:00:00Z",
    expires: str = "2026-11-07T12:00:00Z",
    severity: str = "Severe",
    event_code: str = "wind",
) -> str:
    """Build an invented localized message without captured provider text."""
    return f"""<info>
      <language>{language}</language><category>Met</category>
      <event>Invented event {language}</event>
      <eventCode><valueName>profile:cap:https://alerts.fmi.fi/cap/profile/v1.1.0</valueName>
        <value>{event_code}</value></eventCode>
      <urgency>Immediate</urgency><severity>{severity}</severity><certainty>Likely</certainty>
      <onset>{onset}</onset><expires>{expires}</expires>
      <headline>Invented headline {language}</headline>
      <description>Invented description {language}</description>
      <web>https://en.ilmatieteenlaitos.fi/warnings</web>
      <area><areaDesc>Invented area {language}</areaDesc><polygon>{polygon}</polygon></area>
    </info>"""


def alert(
    identifier: str = "synthetic-one",
    *,
    infos: str | None = None,
    message_type: str = "Alert",
    references: str = "",
    status: str = "Actual",
) -> str:
    """Build an opaque synthetic envelope including optional replacements."""
    body = info() if infos is None else infos
    refs = f"<references>{escape(references)}</references>" if references else ""
    return f"""<alert xmlns="{CAP}">
      <identifier>{identifier}</identifier><sender>{SENDER}</sender><sent>{UPDATED}</sent>
      <status>{status}</status><msgType>{message_type}</msgType><scope>Public</scope>
      {refs}{body}</alert>"""


def feed(*alerts: str, escaped: bool = False) -> bytes:
    """Wrap CAP in a bounded fat Atom publication."""
    entries = "".join(
        '<entry><content type="application/cap+xml">'
        + (escape(item) if escaped else item)
        + "</content></entry>"
        for item in alerts
    )
    return f'<feed xmlns="{ATOM}"><updated>{UPDATED}</updated>{entries}</feed>'.encode()
