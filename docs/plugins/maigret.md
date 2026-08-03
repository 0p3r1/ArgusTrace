# The Maigret plugin

[Maigret](https://github.com/soxoj/maigret) is like Sherlock but with a
much larger site database (3000+ vs ~400) and metadata extraction from
claimed profiles. Pulled from a pinned registry image, same hardening as
Sherlock, plus `-e HOME=/tmp`: Maigret writes its config/database cache
to `$HOME/.maigret` on startup, which fails under `--read-only` at the
default `/root` home.

Maigret's JSON/ndjson report only ever includes `Claimed` (found) sites —
confirmed by reading `generate_json_report` in its source, which hard-skips
anything else. The CSV report doesn't have that limitation, so the plugin
uses `--csv` instead, giving the same three statuses as Sherlock:

| Maigret status | `Status`                                                  |
| -------------- | --------------------------------------------------------- |
| `Claimed`      | `FOUND`                                                   |
| `Available`    | `NOT_FOUND`                                               |
| `Unknown`      | `ERROR` (bot protection, blocked, connection error, etc.) |

Maigret's JSON report is also the only place it exposes extracted profile
data (photo, full name, location, follower counts, ...) and recursive-search
discoveries (other usernames/links found via a claimed page) — both merged
into each `FOUND` finding's `evidence` (`profile`, `related_ids`) by
requesting `--json ndjson` alongside `--csv` in the same run and joining on
site name. `related_ids` drops the exact username searched for (not a new
discovery) but keeps different-casing handles, which are genuinely distinct
per-site.

Exposed options: `timeout`, `retries`, `tags`/`exclude_tags` (free text —
the description embeds the most common tags from a real `--stats` run,
since the web UI has no way to run it), and `enrich` (fetches secondary
API endpoints for even more per-site profile data, slower).
