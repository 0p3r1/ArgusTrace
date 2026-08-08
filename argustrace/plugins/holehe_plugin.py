import json
import re

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import error_finding
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-holehe:1.61"
ENTITY_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUN_TIMEOUT_S = 60

DEFAULT_TIMEOUT_S = 10
TIMEOUT_MIN_S = 5
TIMEOUT_MAX_S = 30


class HolehePlugin:
    name = "holehe"
    supported_entities = ["email"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: does not look like an email address")]

        args = self._build_args(entity, options or {})
        result = await run_hardened(IMAGE, args, timeout_s=RUN_TIMEOUT_S)
        if not result.ok:
            return [self._error(entity, result.error)]
        if result.returncode != 0:
            return [self._error(entity, f"holehe run failed: {result.stderr.decode(errors='replace')[:500]}")]

        try:
            rows = json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return [self._error(entity, "holehe produced no parseable JSON output")]

        return self._parse_rows(entity, rows)

    def _build_args(self, entity: str, options: dict) -> list[str]:
        args = [entity, str(self._resolve_timeout(options))]
        if options.get("no_password_recovery"):
            args.append("-NP")
        return args

    def _resolve_timeout(self, options: dict) -> int:
        try:
            timeout = int(options.get("timeout", DEFAULT_TIMEOUT_S))
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT_S
        return max(TIMEOUT_MIN_S, min(TIMEOUT_MAX_S, timeout))

    def _parse_rows(self, entity: str, rows: list[dict]) -> list[Finding]:
        findings = []
        for row in rows:
            if row["rateLimit"]:
                status = Status.ERROR
            elif row["exists"]:
                status = Status.FOUND
            else:
                status = Status.NOT_FOUND

            evidence = {
                "domain": row.get("domain"),
                "method": row.get("method"),
                "rate_limited": row["rateLimit"],
            }

            recovery_hint = {
                k: v for k, v in {
                    "email": row.get("emailrecovery"),
                    "phone": row.get("phoneNumber"),
                }.items() if v
            }
            if recovery_hint:
                evidence["recovery_hint"] = recovery_hint

            profile = row.get("others") if isinstance(row.get("others"), dict) else None
            if profile:
                evidence["profile"] = profile
                evidence["headline"] = profile.get("FullName") or profile.get("fullname")
            elif row.get("domain") and row.get("method"):
                evidence["headline"] = f"{row['domain']} · {row['method']}"
            evidence = {k: v for k, v in evidence.items() if v}

            findings.append(
                Finding(
                    entity=entity,
                    entity_type="email",
                    source=f"holehe:{row['name']}",
                    status=status,
                    url=f"https://{row['domain']}" if row.get("domain") else None,
                    evidence=evidence,
                )
            )
        return findings

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="email", source="holehe", reason=reason)
