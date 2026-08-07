"""Helpers shared by plugins.

Module-level functions only, deliberately: `Plugin` is a `typing.Protocol`,
and the point of structural typing is that a plugin is anything with the right
shape. Turning any of this into a base class would make inheritance the price
of admission, which is exactly what the Protocol exists to avoid.

What lives here is what was being copy-pasted as the project grew from 3 tools
to 13: the same domain regex in three plugins, the same retry-and-parse ladder
in five, the same error-Finding constructor in fourteen.
"""

import asyncio
import json
from dataclasses import dataclass

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened
from argustrace.settings import SETTINGS

# Hostname per RFC 1035 shape: <=253 chars, dot-separated labels of <=63, and
# an alphabetic TLD. Was verbatim in crtsh, theharvester and wayback.
DOMAIN_PATTERN_SOURCE = r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"

# Conservative across sites; individual tools reject more themselves. Was
# duplicated between sherlock and maigret.
USERNAME_PATTERN_SOURCE = r"^[A-Za-z0-9_.\-]{1,64}$"


def error_finding(entity: str, *, entity_type: str, source: str, reason: str, **evidence) -> Finding:
    """A Finding for something that could not be checked.

    ERROR is not "absent" — it is "we don't know", and conflating the two is
    the false negative the tri-state Status exists to prevent.
    """
    return Finding(
        entity=entity,
        entity_type=entity_type,
        source=source,
        status=Status.ERROR,
        evidence={"reason": reason, **evidence},
    )


def clamp_int(value: object, *, default: int, low: int, high: int) -> int:
    """Coerce to an int inside [low, high], falling back to `default`.

    Values reaching a plugin through the API or CLI have already been
    validated and refused if out of range (see plugins/options.py). This stays
    as defence for direct library callers, who never pass through that.
    """
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


@dataclass(frozen=True)
class JsonFetch:
    """Either parsed JSON, or the reason there isn't any. Never both."""

    data: object | None = None
    error: str | None = None


async def fetch_json(
    url: str,
    *,
    timeout_s: int,
    describe: str,
    image: str | None = None,
    attempts: int = 1,
    delay_s: int = 2,
    expect: type | tuple[type, ...] = (list, dict),
    extra_args: tuple[str, ...] = (),
) -> JsonFetch:
    """Fetch a URL with curl in a hardened container and parse the JSON.

    Collapses the ladder every "fetch a JSON URL" plugin repeated: run,
    distinguish "docker never ran" from "curl failed" from "not JSON", retry
    the transient ones, and give up with a message naming how many attempts
    were made.

    `expect` guards the shape, because "valid JSON" is not the same as "the
    JSON we can parse" — crt.sh answers with an error *object* where the API
    normally returns an array, which used to crash the row parser outright.
    """
    last_error = "unknown error"

    for attempt in range(1, attempts + 1):
        result = await run_hardened(
            image or SETTINGS.curl_image, [*extra_args, url], timeout_s=timeout_s,
        )

        if not result.ok:
            last_error = result.error
        elif result.returncode != 0:
            last_error = f"curl failed: {result.stderr.decode(errors='replace')[:300]}"
        else:
            try:
                data = json.loads(result.stdout.decode(errors="replace"))
            except json.JSONDecodeError:
                last_error = f"{describe} returned a non-JSON or empty response"
            else:
                if isinstance(data, expect):
                    return JsonFetch(data=data)
                last_error = f"{describe} returned an unexpected JSON shape"

        if attempt < attempts:
            await asyncio.sleep(delay_s)

    suffix = f" (after {attempts} attempts)" if attempts > 1 else ""
    return JsonFetch(error=f"{last_error}{suffix}")
