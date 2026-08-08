import csv
import re
import tempfile
from pathlib import Path

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import USERNAME_PATTERN_SOURCE, error_finding
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "sherlock/sherlock@sha256:9d6602b98179fb15ceab88433626fb0ae603ae9880e13cab886970317fe1475f"
ENTITY_PATTERN = re.compile(USERNAME_PATTERN_SOURCE)

# Small, fast-responding set of well-known sites. Checking all ~400+ sites
# that Sherlock knows about takes 1-3 minutes; this default trades recall
# for a sub-10s response time.
CURATED_SITES = [
    "GitHub", "Reddit", "Twitter", "Instagram",
    "YouTube", "GitLab", "Keybase", "Snapchat", "Telegram",
]

FAST_RUN_TIMEOUT_S = 60
FULL_RUN_TIMEOUT_S = 240
DEFAULT_SITE_TIMEOUT_S = 15
SITE_TIMEOUT_MIN_S = 5
SITE_TIMEOUT_MAX_S = 30

# Sherlock's own per-site status, mapped onto our tri-state Status.
# "Illegal" means the username doesn't match that site's naming rules,
# i.e. no check was actually attempted, so those rows are dropped entirely.
SITE_STATUS_MAP = {
    "Claimed": Status.FOUND,
    "Available": Status.NOT_FOUND,
    "Unknown": Status.ERROR,
    "WAF": Status.ERROR,
}


class SherlockPlugin:
    name = "sherlock"
    supported_entities = ["username"]

    def __init__(self, sites: list[str] | None = CURATED_SITES):
        # sites=None means an unrestricted scan across every site Sherlock knows about.
        self.sites = sites
        self.run_timeout_s = FAST_RUN_TIMEOUT_S if sites else FULL_RUN_TIMEOUT_S

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: must match " + ENTITY_PATTERN.pattern)]

        with tempfile.TemporaryDirectory() as tmpdir:
            args = self._build_args(entity, options)

            result = await run_hardened(
                IMAGE, args, volume=(tmpdir, "/output"), timeout_s=self.run_timeout_s,
            )
            if not result.ok:
                return [self._error(entity, result.error)]
            if result.returncode != 0:
                return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]

            csv_path = Path(tmpdir) / f"{entity}.csv"
            if not csv_path.exists():
                return [self._error(entity, "sherlock produced no CSV output")]

            return self._parse_csv(entity, csv_path)

    def _build_args(self, entity: str, options: dict | None) -> list[str]:
        options = options or {}
        try:
            timeout = int(options.get("timeout", DEFAULT_SITE_TIMEOUT_S))
        except (TypeError, ValueError):
            timeout = DEFAULT_SITE_TIMEOUT_S
        timeout = max(SITE_TIMEOUT_MIN_S, min(SITE_TIMEOUT_MAX_S, timeout))

        args = [
            entity,
            "--csv",
            "--folderoutput", "/output",
            "--no-txt",
            "--print-all",
            "--timeout", str(timeout),
        ]
        if options.get("nsfw"):
            args.append("--nsfw")
        for site in self.sites or []:
            args += ["--site", site]
        return args

    def _parse_csv(self, entity: str, csv_path: Path) -> list[Finding]:
        findings = []
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                status = SITE_STATUS_MAP.get(row["exists"])
                if status is None:
                    continue
                findings.append(
                    Finding(
                        entity=entity,
                        entity_type="username",
                        source=f"sherlock:{row['name']}",
                        status=status,
                        url=row["url_user"] or None,
                        evidence={
                            "http_status": row["http_status"],
                            "response_time_s": self._round_response_time(row["response_time_s"]),
                            "site_status": row["exists"],
                        },
                    )
                )
        return findings

    def _round_response_time(self, raw: str) -> str:
        try:
            return str(round(float(raw), 2))
        except (TypeError, ValueError):
            return raw

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="username", source="sherlock", reason=reason)
