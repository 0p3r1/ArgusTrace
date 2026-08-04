# The theHarvester plugin

[theHarvester](https://github.com/laramies/theHarvester) aggregates
subdomains/hosts for a domain from passive recon sources. No official
Docker image exists, so the image clones the official repo at a pinned
release tag (`4.11.1`) and builds it with `uv sync --locked` exactly like
their own Dockerfile, just swapping the entrypoint from the REST server
(`restfulHarvest`) to the CLI (`theHarvester`). Also needs `-e HOME=/tmp`
(same reason as Maigret: default proxies.yaml written on first run).

Only free, no-API-key sources are used. Two variants:

- `theharvester`: a single source (`rapiddns`).
- `theharvester-broad`: four sources combined (`rapiddns,otx,hackertarget,crtsh`).

Like crt.sh, this is a discovery tool rather than a per-candidate check:
every host/IP/email theHarvester reports becomes a `FOUND` Finding; no
results at all → `NOT_FOUND`; a failed run → `ERROR`.

Exposed options: `limit`, `sources` (overrides the fast/broad presets
above), and `dns_lookup` (`-n`, actively resolves hosts the passive sources
found without a resolved address). `-c`/`--dns-brute` and `-t`/`--take-over`
are deliberately **not** exposed: brute force means ~5000 DNS queries
(minutes, not seconds, and arguably active rather than passive recon,
which contradicts this tool's whole reason for being here); take-over
results land in the JSON report as `{url: [{fingerprint: service}, ...]}`,
a shape our generic `name:target`-string parser would mis-handle, and the
check itself actively probes the target's own infrastructure over HTTP —
both were confirmed by reading theHarvester's source, not assumed.

The native XML report re-runs the scan on demand, so it takes the variant
the results came from (`plugin=theharvester-broad`) as a parameter. Without
it, a broad 4-source scan would hand back a single-source report that
quietly disagreed with the results table it was downloaded from.
