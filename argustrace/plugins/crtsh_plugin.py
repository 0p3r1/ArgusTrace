import asyncio
import json
import re
from urllib.parse import quote

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-crtsh:1.0"
ENTITY_PATTERN = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
RUN_TIMEOUT_S = 35

# crt.sh is a free, community-run service that's frequently overloaded
# (502s, 404s, hung connections observed repeatedly in practice). A couple
# of quick retries meaningfully cuts the ERROR rate without hiding a
# genuine, persistent failure.
MAX_ATTEMPTS = 2
RETRY_DELAY_S = 2


class CrtShPlugin:
    name = "crtsh"
    supported_entities = ["domain"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like a domain name")]

        url = f"https://crt.sh/?q={quote(entity)}&output=json"

        last_error = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            result = await run_hardened(IMAGE, [url], timeout_s=RUN_TIMEOUT_S)

            if not result.ok:
                last_error = result.error
            elif result.returncode != 0:
                last_error = f"curl failed: {result.stderr.decode(errors='replace')[:300]}"
            else:
                try:
                    rows = json.loads(result.stdout.decode())
                except json.JSONDecodeError:
                    last_error = "crt.sh returned a non-JSON or empty response (it's a flaky free service)"
                else:
                    return self._parse_rows(entity, rows)

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY_S)

        return [self._error(entity, f"{last_error} (after {MAX_ATTEMPTS} attempts)")]

    def _parse_rows(self, entity: str, rows: list[dict]) -> list[Finding]:
        if not rows:
            return [
                Finding(
                    entity=entity,
                    entity_type="domain",
                    source="crt.sh",
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
                findings.append(
                    Finding(
                        entity=entity,
                        entity_type="domain",
                        source=f"crt.sh:{name}",
                        status=Status.FOUND,
                        url=f"https://crt.sh/?id={row['id']}",
                        evidence={
                            "name": name,
                            "issuer": row.get("issuer_name"),
                            "not_before": row.get("not_before"),
                            "not_after": row.get("not_after"),
                        },
                    )
                )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity,
            entity_type="domain",
            source="crt.sh",
            status=Status.ERROR,
            evidence={"reason": reason},
        )
