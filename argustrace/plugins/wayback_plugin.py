import json
import re
from urllib.parse import quote, urlparse

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-curl:1.0"  # generic curl image, shared with other simple HTTP-API plugins
ENTITY_PATTERN = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
RUN_TIMEOUT_S = 40

# matchType=domain pulls in every host under the domain (subdomains
# included), not just the exact URL — that's the actual OSINT value here
# (surfacing hosts that were once crawled and archived, independent of
# crt.sh's Certificate-Transparency-derived list, a different data source
# that can catch subdomains with no valid cert history at all). Capped to
# keep runtime and payload size reasonable for a "quick recon" tool.
ROW_LIMIT = 2000


class WaybackPlugin:
    name = "wayback"
    supported_entities = ["domain"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like a domain name")]

        url = (
            "http://web.archive.org/cdx/search/cdx"
            f"?url={quote(entity)}&matchType=domain&output=json"
            f"&collapse=urlkey&limit={ROW_LIMIT}&fl=original,timestamp,statuscode"
        )

        result = await run_hardened(IMAGE, [url], timeout_s=RUN_TIMEOUT_S)
        if not result.ok:
            return [self._error(entity, result.error)]
        if result.returncode != 0:
            return [self._error(entity, f"curl failed: {result.stderr.decode(errors='replace')[:300]}")]

        try:
            rows = json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return [self._error(entity, "Wayback Machine returned a non-JSON response")]

        return self._parse_rows(entity, rows)

    def _parse_rows(self, entity: str, rows: list[list[str]]) -> list[Finding]:
        if not rows:
            return [Finding(
                entity=entity, entity_type="domain", source="wayback",
                status=Status.NOT_FOUND, evidence={"reason": "no archived snapshots found for this domain"},
            )]

        # First row is the CDX header (["original", "timestamp", "statuscode"]).
        hosts: dict[str, dict] = {}
        for original, timestamp, statuscode in rows[1:]:
            host = urlparse(original).hostname
            if not host:
                continue
            entry = hosts.setdefault(host, {"first": timestamp, "last": timestamp, "count": 0, "example": original})
            entry["first"] = min(entry["first"], timestamp)
            entry["last"] = max(entry["last"], timestamp)
            entry["count"] += 1
            if statuscode == "200" and entry["example"] == original:
                entry["example"] = original

        findings = []
        for host, data in sorted(hosts.items()):
            first_date = self._format_timestamp(data["first"])
            last_date = self._format_timestamp(data["last"])
            findings.append(Finding(
                entity=entity, entity_type="domain", source=f"wayback:{host}",
                status=Status.FOUND,
                url=f"https://web.archive.org/web/{data['last']}/{data['example']}",
                evidence={
                    "host": host,
                    "first_archived": first_date,
                    "last_archived": last_date,
                    "snapshot_count": data["count"],
                    "headline": f"{data['count']} snapshot{'s' if data['count'] != 1 else ''} · {first_date} → {last_date}",
                },
            ))
        return findings

    def _format_timestamp(self, ts: str) -> str:
        # CDX timestamps are YYYYMMDDhhmmss, always 14 digits.
        if len(ts) < 8:
            return ts
        return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity, entity_type="domain", source="wayback", status=Status.ERROR, evidence={"reason": reason},
        )
