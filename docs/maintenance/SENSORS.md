<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Sensor And Forecast-Supplement Maintenance

Normative entity metadata, values, gust/probability adapters, units, and lightning presentation are
owned by [the sensor contract](../contracts/SENSORS.md). Registry compatibility is owned by
[the migration contract](../contracts/MIGRATIONS.md), and Best-time state is owned by
[the time and missing-data contract](../contracts/TIME_AND_MISSING_DATA.md).

## Adapter Rationale

The selected stable FMI client exposes the core model but its forecast producer does not provide a
usable native `WindGust` value and its model has no probability fields. The narrow adapter in
`custom_components/fmi/fmi_client.py` keeps the extra FMI fields inside one request and outside the
fixed upstream `WeatherData` type. `SNS-003` and `SNS-004` are the authoritative behavior.

## Change Checklist

1. Update the owning `SNS-*` assertion before changing entity metadata, source precedence, or
   presentation attributes.
2. Preserve established unique IDs and device ownership; consult `MIG-*` before any naming change.
3. Test valid zero, missing, malformed, NaN, infinity, unit conversion, and later recovery.
4. For adapter changes, test reordered/missing fields, duplicate timestamps, one-request behavior,
   and the installed-client shape.
5. Run `make reference-contracts`, `make test-full`, `make type-check`, and `make validate`.

## References

- [FMI current producer parameter metadata](https://opendata.fmi.fi/info?what=qengine)
- [FMI WFS examples and parameter guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines)
- [Home Assistant entity naming](https://developers.home-assistant.io/docs/core/entity/)
- [Home Assistant sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Home Assistant entity registry](https://developers.home-assistant.io/docs/entity_registry_index/)
