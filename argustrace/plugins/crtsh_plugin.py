import re
from urllib.parse import quote

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import DOMAIN_PATTERN_SOURCE, error_finding, fetch_json

ENTITY_PATTERN = re.compile(DOMAIN_PATTERN_SOURCE)
# Must stay above the shared curl image's own --max-time plus container
# startup; asserted in tests/test_registry_consistency.py.
RUN_TIMEOUT_S = 35

# crt.sh is a free, community-run service that's frequently overloaded
# (502s, 404s, hung connections observed repeatedly in practice). A couple
# of quick retries meaningfully cuts the ERROR rate without hiding a
# genuine, persistent failure.
MAX_ATTEMPTS = 2
RETRY_DELAY_S = 2

ENTITY_TYPE = "domain"
SOURCE = "crt.sh"


class CrtShPlugin:
    name = "crtsh"
    supported_entities = ["domain"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like a domain name")]

        # expect=list matters: under load crt.sh answers with a JSON error
        # *object* where the API normally returns an array, which used to
        # reach the row parser and crash it.
        fetched = await fetch_json(
            f"https://crt.sh/?q={quote(entity)}&output=json",
            timeout_s=RUN_TIMEOUT_S,
            describe="crt.sh (a flaky, community-run free service)",
            attempts=MAX_ATTEMPTS,
            delay_s=RETRY_DELAY_S,
            expect=list,
        )
        if fetched.error:
            return [self._error(entity, fetched.error)]

        return self._parse_rows(entity, fetched.data)

    def _parse_rows(self, entity: str, rows: list[dict]) -> list[Finding]:
        if not rows:
            return [
                Finding(
                    entity=entity,
                    entity_type=ENTITY_TYPE,
                    source=SOURCE,
                    status=Status.NOT_FOUND,
                    evidence={"reason": "no certificates found in Certificate Transparency logs"},
                )
            ]

        # A domain can have many certs for the same subdomain (reissues, SANs);
        # a name showing up at all means it exists in the CT logs, so dedupe.
        seen = set()
        findings = []
        for row in rows:
            for name in row.get("name_value", "").split("\n"):
                name = name.strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                issuer = row.get("issuer_name")
                not_before = row.get("not_before")
                org = self._issuer_org(issuer)
                issued_on = not_before.split("T")[0] if not_before else None
                headline = " · ".join(p for p in (org, f"issued {issued_on}" if issued_on else None) if p)
                findings.append(
                    Finding(
                        entity=entity,
                        entity_type=ENTITY_TYPE,
                        source=f"{SOURCE}:{name}",
                        status=Status.FOUND,
                        url=f"https://crt.sh/?id={row['id']}",
                        evidence={
                            "name": name,
                            "issuer": issuer,
                            "not_before": not_before,
                            "not_after": row.get("not_after"),
                            **({"headline": headline} if headline else {}),
                        },
                    )
                )
        return findings

    def _issuer_org(self, issuer_name: str | None) -> str | None:
        # issuer_name is a raw certificate DN like "C=US, O=Let's Encrypt,
        # CN=YR2" — the organization ("O=") is the human-readable part
        # worth surfacing, the rest is noise for a quick summary.
        if not issuer_name:
            return None
        match = re.search(r"O=([^,]+)", issuer_name)
        return match.group(1).strip() if match else issuer_name

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type=ENTITY_TYPE, source=SOURCE, reason=reason)
