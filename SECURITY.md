# Security

## Reporting

Open a GitHub issue for anything that is already public. For something that
is not, contact the maintainer privately through their GitHub profile rather
than filing publicly.

This is a hobby project with no SLA. Expect best-effort.

## Threat model

ArgusTrace runs third-party OSINT tools against attacker-influenced input.
Two boundaries carry that risk.

**The container boundary.** Every tool runs in a single-use container with
`--cap-drop=ALL`, `--security-opt=no-new-privileges`, a read-only root
filesystem and memory/CPU/PID limits, and is removed afterwards. Tool output
is treated as untrusted data throughout — that is the whole reason a tool is
never run on the host, and why `HARDENING_FLAGS` is not configurable through
the environment.

**Fetching URLs.** The EXIF plugin fetches a URL the user supplies. Addresses
are validated host-side and then *pinned* for the container with
`--resolve`, so the container performs no DNS lookup of its own; without that
pin a short-TTL record could pass validation and then resolve to an internal
address. Redirects are not followed.

## Do not expose the API

The API can run containers and make the host fetch arbitrary URLs. It is
built for loopback use and `argustrace serve` binds `127.0.0.1` by default;
it refuses any other address unless `ARGUSTRACE_API_TOKEN` is set. Even then,
the token is a single shared secret, not a user system — putting this on a
network you do not control is not a supported configuration.

Native report downloads are plain links and cannot carry the token header, so
they are not covered by it.

## Secrets

The only credential the project handles is the optional Instagram session
cookie for Toutatis. It is passed to the container through an `--env-file`
rather than argv, so it does not appear in the host process list, and it is
never written to logs or included in an error message. It is still your
account's session: use a throwaway.

## What is deliberately not done

No rate limiting — a shared token plus the concurrency ceiling is
proportionate for a single-user local tool. No sandbox escape hardening
beyond Docker's defaults plus the flags above. Container images are pinned by
digest or exact version, but their *contents* are upstream's, not audited
here.
