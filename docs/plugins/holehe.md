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

Like Ignorant, the image doesn't run Holehe's own CLI. Its `maincore()`
calls `check_update()` on **every** invocation — a live PyPI request that,
if a newer release exists, shells out to `pip install --upgrade holehe`
and exits before scanning anything. That means every run phoned home, and
the day upstream ships 1.62 the pinned image would start failing closed
until someone noticed. The image instead bakes in a small wrapper
([`holehe_json.py`](../../docker/holehe/holehe_json.py)) that calls the
library's own module functions directly and prints JSON — which also
sidesteps Holehe's `--timeout` argparse bug (v1.61 stores an explicit
value as a string, making every module raise immediately) and removes the
need to parse its CSV at all.

Each result carries a recovery-email/phone hint and, for a few modules, an
extracted full name or account-creation date (`others`) — merged into
`evidence` as `recovery_hint`/`profile` when present.

Exposed options: `no_password_recovery` (`-NP`) — skips the 4 modules
(Adobe, Mail.ru, Odnoklassniki, Samsung) that trigger a real password-reset
email on the target account, trading a little coverage for a quieter check
— and `timeout`, our wrapper's per-site httpx timeout (see above for why
Holehe's own flag isn't used).
