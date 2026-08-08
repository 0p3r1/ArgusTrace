# The EXIF plugin

Reads embedded metadata from an image with
[exiftool](https://github.com/exiftool/exiftool) — camera model, GPS
coordinates, timestamps, editing history. Two input paths: an `http(s)` URL,
or an uploaded file arriving as a base64 data URI.

No allowlist of accepted formats, on purpose: exiftool reads 100+ of them
(RAW, video, audio, PDF), and hand-maintaining magic-byte signatures would be
a losing game while a prefix match wouldn't stop anything real. Safety comes
from sandboxing the *parser* instead — every run is in the hardened
container, and the upload path additionally gets `--network=none`, since
reading a local file never needs network.

## The URL path and DNS rebinding

Fetching a user-supplied URL is an SSRF surface. The host resolves the
hostname and rejects any non-global address — but validating here and then
handing the container a *hostname* is not enough, because curl resolves it
again inside the container. A short-TTL record can answer with a public
address for our check and `169.254.169.254` for curl's.

So `_validate_url` returns a `host:port:address` pin passed to curl as
`--resolve`, and the container performs no lookup of its own. Every validated
address is pinned, comma-separated: pinning only the first breaks the fetch
outright when DNS returns an AAAA record first and the container has no IPv6
route (observed against upload.wikimedia.org). Redirects stay off for the
same reason the pin exists.

A URL whose host is already a literal address gets no pin — there is no
lookup to rebind, and an IPv6 literal would make the pin ambiguous.

## Uploads

Size is checked on the *encoded* length before decoding: decoding to find out
how big something is materialises the whole payload in memory, which is what
the limit exists to prevent. Findings carry a short label
(`upload:<sha256[:12]> (image/jpeg, 740.9 KB)`) rather than the data URI —
echoing it back turned a 100 MB upload into a ~133 MB response.

## Status mapping

Metadata found → `FOUND`. A file exiftool can read but which carries nothing
beyond baseline filesystem/type keys → `NOT_FOUND`. Anything else — an
unreadable file, a failed fetch, a rejected URL → `ERROR`.

GPS coordinates become the `coordinates` evidence key, which the UI turns
into a map link.
