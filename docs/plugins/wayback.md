# The Wayback Machine plugin

Lists hosts the Internet Archive has ever archived under a domain, with first
and last snapshot dates, via the CDX API. No API key.

`matchType=domain` is what makes this useful: it returns every host under the
domain, subdomains included. That makes it a genuinely different source from
crt.sh — Certificate Transparency only knows about hosts that were issued a
certificate, while the archive knows about anything that was ever crawled,
including hosts with no cert history at all.

Results are grouped by hostname rather than URL, so one finding per host with
a snapshot count and date range, instead of thousands of near-identical rows.

## Truncation is reported, not hidden

The query is capped at `ROW_LIMIT` rows to keep runtime and payload sane for
a recon tool. When exactly that many come back, the real result set may have
been larger, so every finding carries a `truncated` note and the headline
says the counts may be incomplete. Silently reporting a capped count as
though it were the full picture is the same class of error as a guessed
`NOT_FOUND`.

## Status mapping

Any archived host → one `FOUND` per host. No snapshots at all → `NOT_FOUND`.
A failed or unparseable request → `ERROR`.
