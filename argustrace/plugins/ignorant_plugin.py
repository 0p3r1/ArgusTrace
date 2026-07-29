import json

import phonenumbers

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-ignorant:1.2"
RUN_TIMEOUT_S = 60


class IgnorantPlugin:
    name = "ignorant"
    supported_entities = ["phone"]

    async def run(self, entity: str) -> list[Finding]:
        try:
            parsed = phonenumbers.parse(entity, None)
        except phonenumbers.NumberParseException:
            return [self._error(entity, "invalid entity: could not parse as a phone number (use E164, e.g. +33612345678)")]
        if not phonenumbers.is_valid_number(parsed):
            return [self._error(entity, "invalid entity: not a valid phone number")]

        country_code = str(parsed.country_code)
        national_number = str(parsed.national_number)

        result = await run_hardened(
            IMAGE, [country_code, national_number], timeout_s=RUN_TIMEOUT_S,
        )
        if not result.ok:
            return [self._error(entity, result.error)]
        if result.returncode != 0:
            return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]

        try:
            rows = json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return [self._error(entity, "ignorant produced no parseable JSON output")]

        return self._parse_rows(entity, rows)

    def _parse_rows(self, entity: str, rows: list[dict]) -> list[Finding]:
        findings = []
        for row in rows:
            if row["rateLimit"]:
                status = Status.ERROR
            elif row["exists"]:
                status = Status.FOUND
            else:
                status = Status.NOT_FOUND

            findings.append(
                Finding(
                    entity=entity,
                    entity_type="phone",
                    source=f"ignorant:{row['name']}",
                    status=status,
                    url=f"https://{row['domain']}" if row.get("domain") else None,
                    evidence={
                        "domain": row.get("domain"),
                        "method": row.get("method"),
                        "rate_limited": row["rateLimit"],
                    },
                )
            )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity,
            entity_type="phone",
            source="ignorant",
            status=Status.ERROR,
            evidence={"reason": reason},
        )
