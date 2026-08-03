# The Ignorant plugin

[Ignorant](https://github.com/megadose/ignorant) checks whether a phone
number is registered on Amazon, Instagram, and Snapchat — same author and
design as Holehe, same isolation model, also built from a local Dockerfile
(no official image exists).

Ignorant's CLI has no CSV/JSON export, so the image bakes in a small
wrapper ([`ignorant_json.py`](../../docker/ignorant/ignorant_json.py)) that
calls the library's own scan functions directly and prints JSON — more
reliable than parsing colored terminal output. Same status mapping as
Holehe: `rateLimit: true` → `ERROR`, `exists: true` → `FOUND`, otherwise
`NOT_FOUND`.

Entities are parsed with the [`phonenumbers`](https://pypi.org/project/phonenumbers/)
library (Google's libphonenumber) rather than a hand-rolled regex —
splitting a raw number like `+33612345678` into country code (`33`) and
national number (`612345678`) isn't reliably doable with pattern matching,
since country codes vary from 1 to 3 digits with no delimiter in the string.

**Why not PhoneInfoga?** It was the first candidate, but its free (no
API key) scanners don't actually check anything — the "OSINT" scanner
just generates Google search URLs (e.g. `site:instagram.com intext:"+1..."`)
for a human to open and read themselves, and the "local" scanner only
validates formatting/carrier, with no found/not-found signal at all.
Forcing that into `FOUND`/`NOT_FOUND` would misrepresent what was actually
verified, which is exactly what the tri-state `Status` exists to prevent.

Exposed option: `timeout` — Ignorant has no CLI of its own to pass this to
(see above), so it's our own wrapper's hardcoded `httpx` timeout, made
configurable for consistency with every other plugin.
