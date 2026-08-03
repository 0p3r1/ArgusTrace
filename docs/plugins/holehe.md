# The Holehe plugin

[Holehe](https://github.com/megadose/holehe) checks whether an email is
registered on ~120 sites via their "forgot password" flow. Same isolation
as Sherlock (`--cap-drop=ALL`, `--read-only`, `--security-opt=no-new-privileges`,
resource limits), but built from a local Dockerfile pinned to a specific
`pip` version and base image digest, since no official image exists.

Holehe's own per-site result is mapped onto our `Status`:

| Holehe result                  | `Status`    |
| ------------------------------ | ----------- |
| `rateLimit: True`              | `ERROR`     |
| `exists: True`                 | `FOUND`     |
| `exists: False`, no rate limit | `NOT_FOUND` |

Note: Holehe's own code treats _any_ exception raised while checking a site
(network error, parsing failure, actual rate limiting, ...) as `rateLimit:
True` — it's a catch-all, not a precise signal, which is exactly why our
`ERROR` status exists as a separate bucket from `NOT_FOUND`.

The plugin deliberately never passes `--timeout` to Holehe: in v1.61,
argparse stores an explicit value as a string instead of an int, which
makes every single module raise immediately. Omitting the flag keeps the
(int) default and avoids the bug entirely.

Holehe's raw CSV also carries a recovery-email/phone hint and, for a few
modules, an extracted full name or account-creation date (`others`, a
Python-dict-repr string, read back with `ast.literal_eval`) — both were
being silently dropped and are now merged into `evidence` as
`recovery_hint`/`profile` when present.

Exposed option: `no_password_recovery` (`-NP`) — skips the 4 modules
(Adobe, Mail.ru, Odnoklassniki, Samsung) that trigger a real password-reset
email on the target account, trading a little coverage for a quieter check.
