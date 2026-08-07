import asyncio
import ipaddress
import json
from urllib.parse import quote

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened
from argustrace.settings import SETTINGS

IMAGE = SETTINGS.curl_image  # shared "fetch a JSON URL" image
RUN_TIMEOUT_S = 35

RDAP_URL = "https://rdap.org/ip/{ip}"
GEOLOCATION_URL = "http://ip-api.com/json/{ip}"

ALL_SOURCES = ["rdap", "geolocation"]

# rdap.org redirects to whichever RIR actually holds the record, and that
# redirect chain occasionally drops the TLS connection mid-handshake
# (observed directly, not assumed) — a couple of quick retries clears it
# without hiding a genuine, persistent failure. Same rationale as crt.sh.
RDAP_MAX_ATTEMPTS = 2
RDAP_RETRY_DELAY_S = 1


class IPPlugin:
    name = "ip"
    supported_entities = ["ip"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        try:
            addr = ipaddress.ip_address(entity)
        except ValueError:
            return [self._error(entity, "invalid entity: not a valid IPv4/IPv6 address")]
        if not addr.is_global:
            return [self._error(
                entity,
                "invalid entity: not a public, routable IP address "
                "(private, loopback, link-local, or otherwise reserved)",
            )]

        sources = self._resolve_sources(options or {})
        findings = []
        if "rdap" in sources:
            findings.append(await self._rdap(entity))
        if "geolocation" in sources:
            findings.append(await self._geolocation(entity))
        return findings

    def _resolve_sources(self, options: dict) -> list[str]:
        requested = options.get("sources")
        if isinstance(requested, list):
            valid = [s for s in requested if s in ALL_SOURCES]
            if valid:
                return valid
        return ALL_SOURCES

    async def _rdap(self, entity: str) -> Finding:
        url = RDAP_URL.format(ip=quote(entity, safe=":"))

        http_status: int | None = None
        body = ""
        last_error = "unknown error"

        for attempt in range(1, RDAP_MAX_ATTEMPTS + 1):
            result = await run_hardened(
                IMAGE,
                ["-L", "-H", "Accept: application/rdap+json", "-w", "\n%{http_code}", url],
                timeout_s=RUN_TIMEOUT_S,
            )
            if not result.ok:
                last_error = result.error
            elif result.returncode != 0:
                last_error = f"curl failed: {result.stderr.decode(errors='replace')[:300]}"
            else:
                stdout = result.stdout.decode(errors="replace")
                body, _, status_str = stdout.rpartition("\n")
                http_status = int(status_str) if status_str.isdigit() else None
                # A real "no RDAP record" is an honest 404 — trust it right
                # away. Anything else non-2xx (5xx, rate limiting, or an
                # empty body with no status at all) is a transient failure,
                # not a confirmed absence, and shouldn't be folded into the
                # same NOT_FOUND bucket as a genuine 404 — worth retrying
                # instead (verified live: rdap.org can return an empty body
                # with curl exit 0 on a transient upstream error).
                if http_status == 404 or (http_status is not None and 200 <= http_status < 300):
                    break
                last_error = f"RDAP returned HTTP {http_status if http_status is not None else 'unknown'}"

            if attempt < RDAP_MAX_ATTEMPTS:
                await asyncio.sleep(RDAP_RETRY_DELAY_S)

        if http_status == 404:
            return Finding(
                entity=entity, entity_type="ip", source="rdap",
                status=Status.NOT_FOUND, evidence={"reason": "no RDAP record for this address"},
            )
        if http_status is not None and 200 <= http_status < 300:
            return self._parse_rdap(entity, body)
        return self._error(entity, f"{last_error} (after {RDAP_MAX_ATTEMPTS} attempts)", source="rdap")

    def _parse_rdap(self, entity: str, stdout: str) -> Finding:
        if not stdout.strip():
            return self._error(entity, "RDAP returned an empty response despite a successful status", source="rdap")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return self._error(entity, "RDAP returned a non-JSON response", source="rdap")

        organization = self._extract_org_name(data.get("entities"))
        network_name = data.get("name")
        country = data.get("country")

        evidence = {
            "network_name": network_name,
            "handle": data.get("handle"),
            "range": (
                f"{data['startAddress']} - {data['endAddress']}"
                if data.get("startAddress") and data.get("endAddress") else None
            ),
            "status": data.get("status"),
            "country": country,
            "organization": organization,
            "whois_server": data.get("port43"),
            "headline": " · ".join(p for p in (organization or network_name, country) if p) or None,
        }
        evidence = {k: v for k, v in evidence.items() if v}
        return Finding(entity=entity, entity_type="ip", source="rdap", status=Status.FOUND, evidence=evidence)

    def _extract_org_name(self, entities: list[dict] | None) -> str | None:
        for ent in entities or []:
            for prop in (ent.get("vcardArray") or [None, []])[1]:
                if prop[0] == "fn":
                    return prop[3]
        return None

    async def _geolocation(self, entity: str) -> Finding:
        url = GEOLOCATION_URL.format(ip=quote(entity, safe=":"))
        result = await run_hardened(IMAGE, [url], timeout_s=RUN_TIMEOUT_S)
        if not result.ok:
            return self._error(entity, result.error, source="ip-api")
        if result.returncode != 0:
            return self._error(entity, f"curl failed: {result.stderr.decode(errors='replace')[:300]}", source="ip-api")

        return self._parse_geolocation(entity, result.stdout.decode(errors="replace"))

    def _parse_geolocation(self, entity: str, stdout: str) -> Finding:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return self._error(entity, "ip-api.com returned a non-JSON response", source="ip-api")

        if data.get("status") != "success":
            return self._error(entity, data.get("message", "geolocation lookup failed"), source="ip-api")

        city = data.get("city")
        region = data.get("regionName")
        country = data.get("country")

        evidence = {
            "country": country,
            "region": region,
            "city": city,
            "isp": data.get("isp"),
            "org": data.get("org"),
            "as": data.get("as"),
            "coordinates": f"{data['lat']},{data['lon']}" if "lat" in data and "lon" in data else None,
            "headline": ", ".join(p for p in (city, region, country) if p) or None,
        }
        evidence = {k: v for k, v in evidence.items() if v}
        return Finding(entity=entity, entity_type="ip", source="ip-api", status=Status.FOUND, evidence=evidence)

    def _error(self, entity: str, reason: str, source: str = "ip") -> Finding:
        return Finding(entity=entity, entity_type="ip", source=source, status=Status.ERROR, evidence={"reason": reason})
