import csv
import re
import tempfile
from pathlib import Path

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "soxoj/maigret@sha256:aff1954c2c71323368ebb9806efb7e121101d7638736094d4cd3f2b61e7a4fc2"
ENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

FAST_RUN_TIMEOUT_S = 60
FULL_RUN_TIMEOUT_S = 900  # not benchmarked to completion: 3000+ sites, duration varies a lot

# Maigret's own per-site status, mapped onto our tri-state Status.
SITE_STATUS_MAP = {
    "Claimed": Status.FOUND,
    "Available": Status.NOT_FOUND,
    "Unknown": Status.ERROR,
}


class MaigretPlugin:
    name = "maigret"
    supported_entities = ["username"]

    def __init__(self, top_sites: int | None = 15):
        # top_sites=None means -a: every site (3000+) Maigret knows about.
        self.top_sites = top_sites
        self.run_timeout_s = FAST_RUN_TIMEOUT_S if top_sites else FULL_RUN_TIMEOUT_S

    async def run(self, entity: str) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: must match " + ENTITY_PATTERN.pattern)]

        with tempfile.TemporaryDirectory() as tmpdir:
            args = [
                entity,
                "--csv",
                "--folderoutput", "/output",
                "--no-progressbar",
            ]
            args += ["-a"] if self.top_sites is None else ["--top-sites", str(self.top_sites)]

            result = await run_hardened(
                IMAGE, args,
                volume=(tmpdir, "/output"),
                # Maigret writes its config/DB cache to $HOME/.maigret; --read-only
                # blocks the default /root, so point HOME at the writable tmpfs.
                env={"HOME": "/tmp"},
                timeout_s=self.run_timeout_s,
            )
            if not result.ok:
                return [self._error(entity, result.error)]
            if result.returncode != 0:
                return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]

            csv_path = Path(tmpdir) / f"report_{entity}.csv"
            if not csv_path.exists():
                return [self._error(entity, "maigret produced no CSV output")]

            return self._parse_csv(entity, csv_path)

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
                        source=f"maigret:{row['name']}",
                        status=status,
                        url=row["url_user"] or None,
                        evidence={
                            "http_status": row["http_status"],
                            "error_reason": row["error_reason"],
                        },
                    )
                )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity,
            entity_type="username",
            source="maigret",
            status=Status.ERROR,
            evidence={"reason": reason},
        )
