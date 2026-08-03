# The crt.sh plugin

[crt.sh](https://crt.sh) is a public Certificate Transparency log search
service, not a tool — the plugin just makes an HTTP GET to its JSON API
(`?q=<domain>&output=json`). There's no third-party tool code to isolate
here, but it still runs through a container (a minimal Alpine + curl
image) for consistency with every other plugin.

Every certificate name found means "this subdomain exists" — there's no
per-candidate check the way Sherlock has one, so the mapping is: any
result → one `FOUND` Finding per unique subdomain (deduped across
reissues and multi-SAN certificates); an empty result → one `NOT_FOUND`
Finding; a request failure → `ERROR`.

crt.sh is a free, community-run service backed by a single database and
is **frequently overloaded** — we hit 502s, 404s, and hung connections
repeatedly just testing this plugin. The plugin retries once after a
short delay before giving up, which noticeably cuts the failure rate;
if both attempts fail, it still reports `ERROR` honestly rather than
hiding it or retrying forever.
