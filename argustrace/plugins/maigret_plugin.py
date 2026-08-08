import csv
import json
import re
import tempfile
from pathlib import Path

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import error_finding
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "soxoj/maigret@sha256:aff1954c2c71323368ebb9806efb7e121101d7638736094d4cd3f2b61e7a4fc2"
ENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

FAST_RUN_TIMEOUT_S = 60
FULL_RUN_TIMEOUT_S = 900  # not benchmarked to completion: 3000+ sites, duration varies a lot

DEFAULT_SITE_TIMEOUT_S = 30
SITE_TIMEOUT_MIN_S = 5
SITE_TIMEOUT_MAX_S = 60
DEFAULT_RETRIES = 0
RETRIES_MIN = 0
RETRIES_MAX = 3

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

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: must match " + ENTITY_PATTERN.pattern)]

        with tempfile.TemporaryDirectory() as tmpdir:
            args = self._build_args(entity, options)

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

            csv_path = Path(tmpdir) / f"report_{entity}.csv"
            if not csv_path.exists():
                # Verified against the real pinned image: Maigret can exit
                # non-zero *after* successfully writing its reports, because
                # it then tries to update its own site-database cache under
                # site-packages/maigret/resources — blocked by our
                # --read-only hardening, unrelated to the scan itself. Only
                # treat a non-zero exit as a real failure when the report
                # it should have produced is actually missing.
                if result.returncode != 0:
                    return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]
                return [self._error(entity, "maigret produced no CSV output")]

            json_path = Path(tmpdir) / f"report_{entity}_ndjson.json"
            site_extras = self._parse_site_extras(entity, json_path) if json_path.exists() else {}

            return self._parse_csv(entity, csv_path, site_extras)

    def _build_args(self, entity: str, options: dict | None) -> list[str]:
        options = options or {}

        try:
            timeout = int(options.get("timeout", DEFAULT_SITE_TIMEOUT_S))
        except (TypeError, ValueError):
            timeout = DEFAULT_SITE_TIMEOUT_S
        timeout = max(SITE_TIMEOUT_MIN_S, min(SITE_TIMEOUT_MAX_S, timeout))

        try:
            retries = int(options.get("retries", DEFAULT_RETRIES))
        except (TypeError, ValueError):
            retries = DEFAULT_RETRIES
        retries = max(RETRIES_MIN, min(RETRIES_MAX, retries))

        tags = options.get("tags")
        tags = tags.strip() if isinstance(tags, str) and tags.strip() else None

        exclude_tags = options.get("exclude_tags")
        exclude_tags = exclude_tags.strip() if isinstance(exclude_tags, str) and exclude_tags.strip() else None

        args = [
            entity,
            "--csv",
            # Maigret only exposes extracted profile fields (photo, full name,
            # location, follower counts, ...) via its JSON report, never CSV
            # (see report.py: generate_csv_report has no ids_data column).
            # Requesting both keeps CSV as the source of truth for the
            # tri-state status while ndjson enriches the FOUND rows.
            "--json", "ndjson",
            "--folderoutput", "/output",
            "--no-progressbar",
            "--timeout", str(timeout),
            "--retries", str(retries),
        ]
        if tags:
            args += ["--tags", tags]
        if exclude_tags:
            args += ["--exclude-tags", exclude_tags]
        if options.get("enrich"):
            args.append("--enrich")
        args += ["-a"] if self.top_sites is None else ["--top-sites", str(self.top_sites)]
        return args

    def _parse_site_extras(self, entity: str, json_path: Path) -> dict[str, dict]:
        # Maigret's ndjson report (Claimed sites only) carries two things our
        # CSV-derived findings would otherwise miss entirely: extracted
        # profile fields (status.ids — photo, full name, location, ...) and
        # recursive-search discoveries (ids_usernames/ids_links — other
        # accounts/handles found by following links off this claimed page).
        extras = {}
        with json_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                site_extra = {}

                ids = entry.get("status", {}).get("ids")
                if ids:
                    site_extra["profile"] = ids

                # Drop the exact username we searched for — that's not a new
                # discovery. A different casing IS worth keeping: it's the
                # literal handle as used on that specific site.
                other_usernames = {
                    name: id_type
                    for name, id_type in (entry.get("ids_usernames") or {}).items()
                    if name != entity
                }
                links = entry.get("ids_links") or []
                if other_usernames or links:
                    related = {}
                    if other_usernames:
                        related["usernames"] = other_usernames
                    if links:
                        related["links"] = links
                    site_extra["related_ids"] = related

                if site_extra:
                    extras[entry.get("sitename")] = site_extra
        return extras

    def _parse_csv(self, entity: str, csv_path: Path, site_extras: dict[str, dict]) -> list[Finding]:
        findings = []
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                status = SITE_STATUS_MAP.get(row["exists"])
                if status is None:
                    continue
                evidence = {
                    "http_status": row["http_status"],
                    "error_reason": row["error_reason"],
                }
                evidence.update(site_extras.get(row["name"], {}))
                findings.append(
                    Finding(
                        entity=entity,
                        entity_type="username",
                        source=f"maigret:{row['name']}",
                        status=status,
                        url=row["url_user"] or None,
                        evidence=evidence,
                    )
                )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="username", source="maigret", reason=reason)


# Native report generation: a separate, optional capability from the Plugin
# protocol's run(). On-demand only — re-runs the scan fresh, no caching.
REPORT_TOP_SITES = 15  # keep this supplementary action quick
REPORT_FORMATS = {
    "html": {"flag": "-H", "filename": "report_{entity}_plain.html"},
}


async def generate_report(entity: str, report_format: str, plugin: str | None = None) -> bytes:
    # `plugin` (which variant's results are being previewed, e.g.
    # "maigret-full") is accepted for a consistent call signature with
    # other native report generators but deliberately ignored — this report
    # is always the quick top-15-sites version regardless of variant, see
    # REPORT_TOP_SITES above.
    if not ENTITY_PATTERN.match(entity):
        raise ValueError("invalid entity: must match " + ENTITY_PATTERN.pattern)
    spec = REPORT_FORMATS.get(report_format)
    if spec is None:
        raise ValueError(f"unsupported report format for maigret: {report_format!r}")

    with tempfile.TemporaryDirectory() as tmpdir:
        args = [
            entity, spec["flag"],
            "--folderoutput", "/output",
            "--no-progressbar",
            "--top-sites", str(REPORT_TOP_SITES),
        ]
        result = await run_hardened(
            IMAGE, args, volume=(tmpdir, "/output"), env={"HOME": "/tmp"}, timeout_s=FAST_RUN_TIMEOUT_S,
        )
        if not result.ok:
            raise ValueError(result.error)

        report_path = Path(tmpdir) / spec["filename"].format(entity=entity)
        if not report_path.exists():
            # Same non-fatal-nonzero-exit case as run() above — only a real
            # failure if the report itself is missing.
            if result.returncode != 0:
                raise ValueError(f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")
            raise ValueError(f"maigret produced no {report_format} output")
        return report_path.read_bytes()
