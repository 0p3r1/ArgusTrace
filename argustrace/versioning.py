from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx
from packaging.version import InvalidVersion, Version

# Version checks read public, read-only metadata APIs the app itself
# controls the request for — this deliberately bypasses _docker_runner,
# whose sandboxing exists for untrusted third-party *tool* execution, not
# the app's own outbound HTTP reads.
REQUEST_TIMEOUT_S = 10.0
GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}


class VersionStatus(str, Enum):
    CURRENT = "current"
    BEHIND = "behind"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class VersionCheckResult:
    status: VersionStatus
    pinned: str | None = None
    latest: str | None = None
    checked_at: datetime | None = None
    detail: str | None = None


def _classify(pinned: str, releases_newest_first: list[str]) -> VersionCheckResult:
    checked_at = datetime.now(timezone.utc)
    latest = releases_newest_first[0] if releases_newest_first else None

    if pinned not in releases_newest_first:
        # Never guess "outdated" for a version we can't place in the real
        # list (renamed, yanked, or the list fetch was incomplete) — the
        # honest answer is "we don't know", same discipline as Docker
        # failures becoming ERROR rather than a guessed negative result.
        return VersionCheckResult(
            VersionStatus.UNKNOWN, pinned=pinned, latest=latest, checked_at=checked_at,
            detail="pinned version not found in fetched release list",
        )

    index = releases_newest_first.index(pinned)
    if index == 0:
        status = VersionStatus.CURRENT
    elif index == 1:
        status = VersionStatus.BEHIND
    else:
        status = VersionStatus.OUTDATED
    return VersionCheckResult(status, pinned=pinned, latest=latest, checked_at=checked_at)


def _unknown(pinned: str, detail: str) -> VersionCheckResult:
    return VersionCheckResult(
        VersionStatus.UNKNOWN, pinned=pinned, checked_at=datetime.now(timezone.utc), detail=detail,
    )


async def check_pypi(package: str, pinned: str) -> VersionCheckResult:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            resp = await client.get(f"https://pypi.org/pypi/{package}/json")
            resp.raise_for_status()
            releases = list(resp.json().get("releases", {}).keys())
    except Exception as e:
        return _unknown(pinned, str(e))

    def sort_key(v: str) -> tuple[int, Version | str]:
        try:
            return (1, Version(v))
        except InvalidVersion:
            return (0, v)  # unparseable versions sink below real ones

    releases_sorted = sorted(releases, key=sort_key, reverse=True)
    return _classify(pinned, releases_sorted)


async def check_dockerhub(repository: str, pinned: str) -> VersionCheckResult:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            resp = await client.get(
                f"https://hub.docker.com/v2/repositories/{repository}/tags",
                params={"page_size": 100, "ordering": "last_updated"},
            )
            resp.raise_for_status()
            tags = [r["name"] for r in resp.json().get("results", []) if r.get("name") != "latest"]
    except Exception as e:
        return _unknown(pinned, str(e))

    return _classify(pinned, tags)


async def check_github_releases(repo: str, pinned: str) -> VersionCheckResult:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers=GITHUB_HEADERS) as client:
            resp = await client.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 100})
            resp.raise_for_status()
            releases = [r["tag_name"] for r in resp.json() if not r.get("draft")]
            if not releases:
                # Not every project cuts GitHub Releases; fall back to tags.
                # Without per_page, GitHub defaults to 30 — verified live
                # against exiftool/exiftool: our pin sat just past that
                # default page, past every actual release since, producing
                # a false "unknown" instead of the real "outdated by N".
                resp = await client.get(f"https://api.github.com/repos/{repo}/tags", params={"per_page": 100})
                resp.raise_for_status()
                releases = [t["name"] for t in resp.json()]
    except Exception as e:
        return _unknown(pinned, str(e))

    return _classify(pinned, releases)


# Plain in-memory cache, no TTL/persistence — consistent with "on-demand
# only, no scheduler": a restart resets every badge to unknown, which is
# the correct consequence of that constraint, not an oversight.
_cache: dict[str, VersionCheckResult] = {}


async def check(family: str, version_check: dict) -> VersionCheckResult:
    method = version_check.get("method", "none")
    if method == "none":
        result = VersionCheckResult(VersionStatus.NOT_APPLICABLE)
    elif method == "pypi":
        result = await check_pypi(version_check["package"], version_check["pinned_version"])
    elif method == "dockerhub":
        result = await check_dockerhub(version_check["repository"], version_check["pinned_version"])
    elif method == "github_releases":
        result = await check_github_releases(version_check["repo"], version_check["pinned_version"])
    else:
        result = _unknown(version_check.get("pinned_version"), f"unknown version_check method: {method!r}")

    _cache[family] = result
    return result


def cached(family: str) -> VersionCheckResult | None:
    return _cache.get(family)
