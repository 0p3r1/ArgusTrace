import json
import re

from argustrace.core.models import Finding, Status
from argustrace.plugins._common import error_finding
from argustrace.plugins._docker_runner import run_hardened

# Built from a pinned commit (see docker/toutatis/Dockerfile), not a PyPI
# release — PyPI's latest (1.31) predates a real API cleanup upstream.
IMAGE = "argustrace-toutatis:1.0"
RUN_TIMEOUT_S = 30

ENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.]{1,30}$")

# toutatis's own core.py (verified against the real source, not just its
# README/CLI) returns these as literal strings on failure — not an
# exhaustive protocol, just what the library actually produces.
CONFIRMED_ABSENT_ERRORS = {"User not found"}


class ToutatisPlugin:
    name = "toutatis"
    supported_entities = ["username"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        if not ENTITY_PATTERN.match(entity):
            return [self._error(entity, "invalid entity: not a valid Instagram username")]

        session_id = (options or {}).get("session_id") or ""
        env = {"IG_SESSIONID": session_id} if session_id else None

        result = await run_hardened(IMAGE, [entity], timeout_s=RUN_TIMEOUT_S, env=env)
        if not result.ok:
            return [self._error(entity, result.error)]
        if result.returncode != 0:
            return [self._error(entity, f"docker run failed: {result.stderr.decode(errors='replace')[:500]}")]

        try:
            data = json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return [self._error(entity, "toutatis produced no parseable JSON output")]

        return self._parse_result(entity, data)

    def _parse_result(self, entity: str, data: dict) -> list[Finding]:
        profile = data.get("profile") or {}
        error = profile.get("error")

        if error in CONFIRMED_ABSENT_ERRORS:
            return [Finding(
                entity=entity, entity_type="username", source="toutatis",
                status=Status.NOT_FOUND, evidence={"reason": "no Instagram account with this username"},
            )]
        user = profile.get("user")
        if not user:
            # Verified against the real API: toutatis's own error handling
            # doesn't distinguish a genuine lookup failure from Instagram
            # rate-limiting/blocking an unauthenticated request (both surface
            # as the same generic "Not found"/"Rate limit" string) — without
            # a session cookie this happens after just a handful of requests
            # in practice. Either way we didn't get to verify anything, so
            # never guess NOT_FOUND here.
            return [self._error(
                entity,
                f"could not verify ({error or 'no profile data returned'}) — Instagram likely "
                "rate-limited or blocked this request; without a session cookie this happens "
                "quickly, provide one for reliable results",
            )]

        evidence = self._build_evidence(user, data.get("lookup") or {})
        return [Finding(
            entity=entity, entity_type="username", source="toutatis",
            status=Status.FOUND, url=f"https://www.instagram.com/{entity}/", evidence=evidence,
        )]

    def _build_evidence(self, user: dict, lookup: dict) -> dict:
        # Maigret-style profile dict (fullname/follower_count/image) so the
        # results table renders a photo + name row the same way it does for
        # every other username-lookup plugin, instead of a bespoke shape.
        profile = {}
        if user.get("full_name"):
            profile["fullname"] = user["full_name"]
        if user.get("follower_count") is not None:
            profile["follower_count"] = user["follower_count"]
        # Without a session cookie, Instagram's response is heavily redacted
        # (id/username/profile pic only, verified directly against the real
        # API) — hd_profile_pic_url_info is only present with a session.
        pic = (user.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url")
        if pic:
            profile["image"] = pic

        evidence = {
            "is_verified": user.get("is_verified"),
            "is_business": user.get("is_business"),
            "is_private": user.get("is_private"),
            "following_count": user.get("following_count"),
            "media_count": user.get("media_count"),
            "biography": user.get("biography"),
            "external_url": user.get("external_url"),
            "public_email": user.get("public_email"),
            "public_phone_number": user.get("public_phone_number"),
        }
        if profile:
            evidence["profile"] = profile

        lookup_user = lookup.get("user") or {}
        if not lookup.get("error"):
            if lookup_user.get("obfuscated_email"):
                evidence["obfuscated_email"] = lookup_user["obfuscated_email"]
            if lookup_user.get("obfuscated_phone"):
                evidence["obfuscated_phone"] = lookup_user["obfuscated_phone"]

        evidence = {k: v for k, v in evidence.items() if v is not None and v != ""}

        headline_parts = []
        if profile.get("fullname"):
            headline_parts.append(profile["fullname"])
        if user.get("is_private"):
            headline_parts.append("private account")
        if "obfuscated_email" in evidence or "obfuscated_phone" in evidence:
            headline_parts.append("obfuscated contact recovered")
        if not headline_parts and not profile.get("fullname"):
            # Confirmed the account exists (we got an id/username back), but
            # Instagram redacts everything else without a session cookie.
            headline_parts.append("account exists — limited data without a session cookie")
        if headline_parts:
            evidence["headline"] = " · ".join(headline_parts)

        return evidence

    def _error(self, entity: str, reason: str) -> Finding:
        return error_finding(entity, entity_type="username", source="toutatis", reason=reason)
