import json
import re
import tempfile
from pathlib import Path

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-theharvester:4.11.1"
ENTITY_PATTERN = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")

# All free, no-API-key-required sources. "broad" combines several passive
# sources for more coverage at the cost of a longer run.
FAST_SOURCES = "rapiddns"
BROAD_SOURCES = "rapiddns,otx,hackertarget,crtsh"

FAST_RUN_TIMEOUT_S = 45
BROAD_RUN_TIMEOUT_S = 120

DEFAULT_LIMIT = 500
LIMIT_MIN = 100
LIMIT_MAX = 1000
ALLOWED_SOURCES = {"rapiddns", "otx", "hackertarget", "crtsh"}


class TheHarvesterPlugin:
    name = "theharvester"
    supported_entities = ["domain"]

    def __init__(self, sources: str = FAST_SOURCES):
        self.sources = sources
        self.run_timeout_s = FAST_RUN_TIMEOUT_S if sources == FAST_SOURCES else BROAD_RUN_TIMEOUT_S

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like a domain name")]

        options = options or {}
        sources = self._resolve_sources(options)

        with tempfile.TemporaryDirectory() as tmpdir:
            args = self._build_args(entity, options, sources)

            result = await run_hardened(
                IMAGE, args,
                volume=(tmpdir, "/output"),
                # theHarvester writes a default proxies.yaml to $HOME/.theHarvester
                # on first run; --read-only blocks the default /home/theharvester.
                env={"HOME": "/tmp"},
                timeout_s=self.run_timeout_s,
            )
            if not result.ok:
                return [self._error(entity, result.error)]
            if result.returncode != 0:
                return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]

            json_path = Path(tmpdir) / "report.json"
            if not json_path.exists():
                return [self._error(entity, "theHarvester produced no JSON output")]

            try:
                data = json.loads(json_path.read_text())
            except json.JSONDecodeError:
                return [self._error(entity, "theHarvester produced unparseable JSON")]

            return self._parse_report(entity, data, sources)

    def _resolve_sources(self, options: dict) -> str:
        sources_override = options.get("sources")
        if isinstance(sources_override, list):
            valid = [s for s in sources_override if s in ALLOWED_SOURCES]
            if valid:
                return ",".join(valid)
        return self.sources

    def _build_args(self, entity: str, options: dict, sources: str) -> list[str]:
        try:
            limit = int(options.get("limit", DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        limit = max(LIMIT_MIN, min(LIMIT_MAX, limit))

        return ["-d", entity, "-b", sources, "-l", str(limit), "-f", "/output/report"]

    def _parse_report(self, entity: str, data: dict, sources: str) -> list[Finding]:
        # A single host can have multiple DNS records (A + AAAA, dual-stack);
        # theHarvester lists each "name:resolved_target" pair separately, so
        # group by (category, name) and collect every resolved target instead
        # of emitting one confusingly-identical-looking row per record.
        grouped: dict[tuple[str, str], list[str]] = {}
        for category, items in data.items():
            if category == "cmd" or not items:
                continue
            for item in items:
                name, _, target = item.partition(":")
                grouped.setdefault((category, name), []).append(target or None)

        findings = []
        for (category, name), resolved in grouped.items():
            findings.append(
                Finding(
                    entity=entity,
                    entity_type="domain",
                    source=f"theharvester:{category}:{name}",
                    status=Status.FOUND,
                    url=f"https://{name}" if category == "hosts" else None,
                    evidence={"name": name, "resolved": resolved},
                )
            )

        if not findings:
            return [
                Finding(
                    entity=entity,
                    entity_type="domain",
                    source="theharvester",
                    status=Status.NOT_FOUND,
                    evidence={"reason": f"no results from source(s): {sources}"},
                )
            ]
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity,
            entity_type="domain",
            source="theharvester",
            status=Status.ERROR,
            evidence={"reason": reason},
        )
