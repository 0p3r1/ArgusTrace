import asyncio
import re
from urllib.parse import quote

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import error_finding, fetch_json

# Must stay above the shared curl image's own --max-time plus container
# startup, so curl aborts with a clean error instead of the outer docker
# timeout killing the container mid-request. Asserted in
# tests/test_registry_consistency.py.
RUN_TIMEOUT_S = 35

GENDERIZE_URL = "https://api.genderize.io/?name={name}"
AGIFY_URL = "https://api.agify.io/?name={name}"
NATIONALIZE_URL = "https://api.nationalize.io/?name={name}"

# A first name, not a full "First Last" — the APIs are trained on single
# given names and get noticeably less accurate (and sometimes just wrong)
# fed a multi-word string. Letters (incl. accents), hyphens, apostrophes,
# e.g. "Jean-Pierre", "O'Brien", "José".
ENTITY_PATTERN = re.compile(r"^[^\W\d_]+(?:['\-][^\W\d_]+)*$", re.UNICODE)
MAX_LENGTH = 50


class NamePlugin:
    name = "name"
    supported_entities = ["name"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        entity = entity.strip()
        if len(entity) > MAX_LENGTH or not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: expected a single first name (letters, hyphen, apostrophe only)")]

        encoded = quote(entity)
        gender_result, age_result, nationality_result = await asyncio.gather(
            self._fetch(GENDERIZE_URL.format(name=encoded), "genderize"),
            self._fetch(AGIFY_URL.format(name=encoded), "agify"),
            self._fetch(NATIONALIZE_URL.format(name=encoded), "nationalize"),
        )

        errors = [r for r in (gender_result, age_result, nationality_result) if isinstance(r, str)]
        if len(errors) == 3:
            return [self._error(entity, "; ".join(errors))]

        gender_data = gender_result if isinstance(gender_result, dict) else None
        age_data = age_result if isinstance(age_result, dict) else None
        nationality_data = nationality_result if isinstance(nationality_result, dict) else None

        return [self._build_finding(entity, gender_data, age_data, nationality_data, errors)]

    async def _fetch(self, url: str, label: str) -> dict | str:
        fetched = await fetch_json(
            url, timeout_s=RUN_TIMEOUT_S, describe=f"{label} (likely rate-limited)", expect=dict,
        )
        if fetched.error:
            return f"{label}: {fetched.error}"
        parsed = fetched.data
        if isinstance(parsed, dict) and parsed.get("error"):
            # These APIs return HTTP 429 with a *valid* JSON error body (e.g.
            # {"error": "Request limit reached"}) on daily rate limit —
            # verified directly. curl doesn't treat that as a failure (no
            # -f), so this has to be caught explicitly or a rate limit
            # silently reads as "no data for this name", a NOT_FOUND that
            # was never actually verified.
            return f"{label}: {parsed['error']}"
        return parsed

    def _build_finding(
        self, entity: str, gender_data: dict | None, age_data: dict | None,
        nationality_data: dict | None, errors: list[str],
    ) -> Finding:
        no_gender_signal = not gender_data or gender_data.get("gender") is None
        no_age_signal = not age_data or age_data.get("age") is None
        no_nationality_signal = not nationality_data or not nationality_data.get("country")

        if no_gender_signal and no_age_signal and no_nationality_signal and not errors:
            # All three genuinely responded (no errors) with an empty dataset
            # for this name — a real, verified "we have no data" answer.
            return Finding(
                entity=entity, entity_type="name", source="name-analysis",
                status=Status.NOT_FOUND, evidence={"reason": "no statistical data found for this name"},
            )

        evidence: dict = {}
        if gender_data and gender_data.get("gender"):
            evidence["gender"] = gender_data["gender"]
            evidence["gender_probability"] = gender_data.get("probability")
        if age_data and age_data.get("age") is not None:
            evidence["estimated_age"] = age_data["age"]
        if nationality_data and nationality_data.get("country"):
            top = sorted(nationality_data["country"], key=lambda c: -c["probability"])[:5]
            evidence["likely_countries"] = [f"{c['country_id']} ({c['probability']:.0%})" for c in top]

        if errors:
            evidence["reason"] = "partial data — some sources failed: " + "; ".join(errors)

        headline_parts = []
        if evidence.get("gender"):
            headline_parts.append(f"{evidence['gender']} ({evidence['gender_probability']:.0%})")
        if evidence.get("estimated_age") is not None:
            headline_parts.append(f"~{evidence['estimated_age']} y/o")
        if evidence.get("likely_countries"):
            headline_parts.append(evidence["likely_countries"][0])
        if headline_parts:
            evidence["headline"] = " · ".join(headline_parts)

        status = Status.FOUND if headline_parts else Status.ERROR
        return Finding(entity=entity, entity_type="name", source="name-analysis", status=status, evidence=evidence)

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="name", source="name-analysis", reason=reason)
