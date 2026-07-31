import csv
import glob
import re
import tempfile
from pathlib import Path

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-holehe:1.61"
ENTITY_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUN_TIMEOUT_S = 60


class HolehePlugin:
    name = "holehe"
    supported_entities = ["email"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like an email address")]

        with tempfile.TemporaryDirectory() as tmpdir:
            args = self._build_args(entity, options or {})

            result = await run_hardened(
                IMAGE, args, volume=(tmpdir, "/home/holehe"), timeout_s=RUN_TIMEOUT_S,
            )
            if not result.ok:
                return [self._error(entity, result.error)]

            # holehe's own --csv handler calls exit("message") on success,
            # which raises SystemExit(1) — a non-zero code here does not
            # mean failure, so we check for the output file instead.
            matches = glob.glob(str(Path(tmpdir) / "holehe_*_results.csv"))
            if not matches:
                reason = result.stderr.decode(errors="replace")[:500] or "no CSV output produced"
                return [self._error(entity, f"holehe run failed: {reason}")]

            return self._parse_csv(entity, Path(matches[0]))

    def _build_args(self, entity: str, options: dict) -> list[str]:
        # Deliberately not passing --timeout: holehe 1.61's argparse stores
        # an explicit value as a string instead of an int, which makes
        # every module raise immediately.
        args = [entity, "--csv"]
        if options.get("no_password_recovery"):
            args.append("-NP")
        return args

    def _parse_csv(self, entity: str, csv_path: Path) -> list[Finding]:
        findings = []
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["rateLimit"] == "True":
                    status = Status.ERROR
                elif row["exists"] == "True":
                    status = Status.FOUND
                else:
                    status = Status.NOT_FOUND

                findings.append(
                    Finding(
                        entity=entity,
                        entity_type="email",
                        source=f"holehe:{row['name']}",
                        status=status,
                        url=f"https://{row['domain']}" if row["domain"] else None,
                        evidence={
                            "domain": row["domain"],
                            "method": row["method"],
                            "rate_limited": row["rateLimit"],
                        },
                    )
                )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity,
            entity_type="email",
            source="holehe",
            status=Status.ERROR,
            evidence={"reason": reason},
        )
