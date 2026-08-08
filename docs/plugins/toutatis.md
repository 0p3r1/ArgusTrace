# The Toutatis plugin

[Toutatis](https://github.com/megadose/toutatis) extracts Instagram profile
information for a username — bio, follower counts, and an obfuscated
email/phone when a session is supplied.

## The session cookie

This is the project's one exception to "no API keys the user has to
provision", and it is opt-in. Verified against the real API: without a
session cookie Instagram returns heavily redacted data for perhaps the first
request and then rate-limits or blocks the rest, so a cookie is needed for
reliable use — not merely for the obfuscated contact lookup.

Supplying one has real consequences, stated in the option description rather
than buried here: using a real account's session for automated requests
violates Instagram's Terms of Service and risks that account being flagged or
banned. Use a throwaway account.

The cookie is declared as a `secret` option, which means the web UI masks it
and `plugins/options.py` never echoes it back in a validation error. It
reaches the container through an `--env-file`, not `-e KEY=value`, so it does
not appear in the host's process list.

## Pinning

Pinned to a specific upstream commit rather than a release: PyPI's latest
(1.31) predates an API cleanup on GitHub, verified by running 1.31 and
hitting a crash the newer source doesn't have. No git tags exist for the
repo, so `version_check` is `none` — there is nothing meaningful to compare
against.

## Status mapping

The image runs a small wrapper
([`toutatis_json.py`](../../docker/toutatis/toutatis_json.py)) that calls the
library directly and prints JSON, catching exceptions so a crash comes back
as a clean message instead of a raw traceback in the finding.

Only "User not found" counts as a confirmed absence (`NOT_FOUND`). Everything
else — a rate limit, a redacted response, a crash — is `ERROR`, because none
of them establish that the account doesn't exist. When Instagram returns an
account with its fields redacted, the headline says so rather than implying
the profile is empty.
