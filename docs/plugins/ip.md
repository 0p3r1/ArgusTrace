# The IP plugin

Two independent, zero-authentication sources, both run through the same
generic curl image as crt.sh — no API keys, no signup:

- **RDAP** (`rdap.org`, redirecting to whichever RIR — ARIN/RIPE/APNIC/
  LACNIC/AFRINIC — actually holds the record): network allocation, org
  name, and status. The redirect chain occasionally drops the TLS
  connection mid-handshake (observed directly, not assumed) — a couple of
  quick retries clears it, same rationale as crt.sh's flakiness handling.
  The retry decision reads curl's **HTTP status**, not just whether a body
  came back: verified live, rdap.org answers a genuine "no record" with a
  404 and an empty body, but can also return an empty body on a transient
  5xx — and curl exits 0 either way. Only the 404 is `NOT_FOUND`;
  everything else is retried and, if it never clears, reported as `ERROR`
  rather than a confident "no record".
- **ip-api.com**: approximate city-level geolocation, ISP, and ASN.

Private, loopback, link-local, and other non-routable addresses (RFC 1918,
`::1`, etc.) are rejected up front with Python's `ipaddress` module
(`is_global`) rather than sent to either source — there's no public OSINT
data for an address that isn't actually routable on the internet, and both
APIs would otherwise report that fact in their own inconsistent ways (RDAP
returns a "reserved" record, ip-api.com returns `status: fail`). Both
sources run independently per lookup, so one failing doesn't lose the
other's result. Exposed option: `sources` (run RDAP, geolocation, or both).
