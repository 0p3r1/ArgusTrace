# The VATComply plugin

Validates an EU VAT number and returns the registered company name and
address, via [VATComply](https://www.vatcomply.com), which proxies the EU's
own VIES system. Covers every EU member state, so it complements the
France-only Recherche d'entreprises plugin. No API key.

The entity regex is deliberately loose — two letters plus 2-12 alphanumerics
— because the real format varies a lot per country. VIES itself is the
authority on validity, and its verdict is what gets reported.

## Transient versus permanent failures

VIES is regularly overloaded: a real, valid, currently-registered VAT number
came back `MS_MAX_CONCURRENT_REQ` on two of three consecutive attempts when
this was tested. That is a statement about the gateway, not the company, so
those are retried.

Telling the two apart is not just `INVALID_INPUT`, which was the original
assumption. Verified live, VATComply returns full-sentence `detail` messages
for genuinely permanent problems — a per-country format error gives "Invalid
VAT number format. Expected format: …", and any GB number gives a message
about the VoW service having ceased in 2021. Those were being retried three
times for nothing before still failing.

The distinguishing rule is the shape: VIES gateway codes are short ALL_CAPS
identifiers, so anything that isn't fails fast and is reported as-is.

## Status mapping

VIES says valid → `FOUND` with whatever name and address it returns (the
service uses `---` for fields it won't disclose, which are dropped rather
than shown). VIES says not valid → `NOT_FOUND`, a real answer about a real
registry. Anything that prevented an answer → `ERROR`.
