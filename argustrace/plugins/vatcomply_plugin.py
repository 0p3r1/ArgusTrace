import asyncio
import re
from urllib.parse import quote

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import error_finding, fetch_json

# Must stay above the shared curl image's own --max-time plus container
# startup; asserted in tests/test_registry_consistency.py.
RUN_TIMEOUT_S = 35

# EU VAT numbers: 2-letter country code + up to 12 alphanumeric chars —
# actual format varies a lot per country, so this is deliberately loose;
# the API itself is the real validator (see VATComply's own 400 response).
ENTITY_PATTERN = re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{2,12}$")

# VATComply proxies the EU's own VIES system, which is well known to be
# flaky/overloaded — verified directly: a real, valid, existing VAT number
# came back "MS_MAX_CONCURRENT_REQ" on 2 of 3 consecutive attempts. That is
# a transient upstream error, not a statement about the entity — only
# INVALID_INPUT actually means the number itself is malformed.
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 2

# VIES gateway error codes are short, ALL_CAPS identifiers (e.g.
# "MS_MAX_CONCURRENT_REQ", "SERVICE_UNAVAILABLE") — genuinely transient,
# worth retrying. Any other `detail` is a full-sentence message VATComply
# generates for a real, permanent problem — verified live for two cases a
# naive "any detail = retry" check used to retry 3 times pointlessly
# before still correctly failing: "FRAB" -> "Invalid VAT number format.
# Expected format: ..." and any GB number -> "...VoW service ceased to
# exist...". Full sentences never match this pattern, so they fail fast.
TRANSIENT_DETAIL_PATTERN = re.compile(r"^[A-Z_]+$")


class VatComplyPlugin:
    name = "vatcomply"
    supported_entities = ["company"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        cleaned = entity.strip().replace(" ", "").upper()
        if not ENTITY_PATTERN.match(cleaned):
            return [self._error(entity, "invalid entity: expected an EU VAT number, e.g. FR40303265045")]

        url = f"https://api.vatcomply.com/vat?vat_number={quote(cleaned)}"

        last_error = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            fetched = await fetch_json(
                url, timeout_s=RUN_TIMEOUT_S, describe="VATComply", expect=dict,
            )

            if fetched.error:
                last_error = fetched.error
            else:
                detail = fetched.data.get("detail")
                if detail == "INVALID_INPUT":
                    return [self._error(entity, "invalid entity: not a valid EU VAT number format")]
                if detail and not TRANSIENT_DETAIL_PATTERN.match(detail):
                    # A full-sentence detail is a permanent, non-retryable
                    # problem, not a transient VIES gateway hiccup.
                    return [self._error(entity, detail)]
                if detail:
                    # EU VIES member-state gateway error (overloaded,
                    # unavailable, ...) — transient, worth retrying.
                    last_error = f"EU VIES system error: {detail}"
                else:
                    return self._parse_response(entity, fetched.data)

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_S)

        return [self._error(entity, f"{last_error} (after {MAX_ATTEMPTS} attempts)")]

    def _parse_response(self, entity: str, data: dict) -> list[Finding]:
        if not data.get("valid"):
            return [Finding(
                entity=entity, entity_type="company", source="vatcomply",
                status=Status.NOT_FOUND, evidence={"reason": "not a registered EU VAT number"},
            )]

        name = data.get("name")
        address = data.get("address")
        evidence = {
            "country_code": data.get("country_code"),
            "name": None if name == "---" else name,
            "address": None if address == "---" else address,
        }
        evidence = {k: v for k, v in evidence.items() if v}
        if evidence.get("name"):
            evidence["headline"] = evidence["name"]

        return [Finding(
            entity=entity, entity_type="company", source="vatcomply", status=Status.FOUND, evidence=evidence,
        )]

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="company", source="vatcomply", reason=reason)
