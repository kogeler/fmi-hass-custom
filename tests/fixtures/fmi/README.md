# FMI Fixture Metadata

All fixtures in this directory are synthetic and deterministic. Weather values were constructed for tests, place coordinates are rounded public city/locality coordinates, and no response was captured from the FMI service. They therefore contain no owner coordinates, secrets, or FMI-licensed source dataset.

If a future test adds captured FMI public data, its fixture metadata must record:

- the FMI endpoint and stored query identifier;
- capture time in UTC;
- requested time range and rounded/sanitized location;
- sanitization performed;
- FMI attribution and the applicable data-license URL.

Ordinary test collection must only read these local files and must never refresh them from the network.
