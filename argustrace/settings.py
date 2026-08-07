"""Runtime configuration, read once from the environment.

Only things an operator may legitimately need to change live here. Some
constants are deliberately *not* configurable:

- `HARDENING_FLAGS` (`plugins/_docker_runner.py`) — an environment variable
  able to drop `--cap-drop=ALL` would itself be the vulnerability.
- The digest-pinned upstream image references in each plugin — pinning is a
  supply-chain invariant, not a preference.
- Per-plugin timeouts and entity regexes — they encode what a given tool and
  API actually do, and are asserted against each other in the test suite.
"""

import os
from dataclasses import dataclass

ENV_PREFIX = "ARGUSTRACE_"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _int_env(name: str, default: int, *, lo: int, hi: int) -> int:
    try:
        value = int(_env(name, str(default)))
    except ValueError:
        return default
    return max(lo, min(hi, value))


def _float_env(name: str, default: float, *, lo: float, hi: float) -> float:
    try:
        value = float(_env(name, str(default)))
    except ValueError:
        return default
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class Settings:
    #: Shared secret required on every API request. Empty means no auth,
    #: which is the right default for the loopback-only local use this tool
    #: is built for — but the server refuses to bind a non-loopback address
    #: without one (see `cli.serve`).
    api_token: str | None
    #: Browser origins allowed to call the API. Only the Vite dev server by
    #: default; the API is not meant to be reachable from anywhere else.
    cors_origins: tuple[str, ...]
    #: Ceiling on containers running at once. Every container is allowed
    #: 512 MB, so without a ceiling N simultaneous requests means N x 512 MB
    #: and N full tool scans competing for the same network.
    max_concurrent_runs: int
    #: Multiplier applied to every container timeout, for slow links or
    #: overloaded machines. One knob instead of ~24 environment variables,
    #: and it can only lengthen: several plugins must outlast the timeout
    #: their container applies internally (see the curl image's --max-time,
    #: asserted in tests/test_registry_consistency.py), and shortening them
    #: would resurrect exactly the bug that test exists to prevent.
    timeout_scale: float
    #: Tag of the shared curl image. Every "fetch a JSON URL" plugin uses it,
    #: so it lives here rather than being repeated in each of them. The
    #: digest-pinned upstream images (Sherlock, Maigret) are deliberately not
    #: overridable — pinning them is a supply-chain invariant, not a setting.
    curl_image: str
    #: Root logger level.
    log_level: str


def load() -> Settings:
    return Settings(
        api_token=_env("API_TOKEN", "").strip() or None,
        cors_origins=tuple(
            origin.strip()
            for origin in _env("CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ),
        max_concurrent_runs=_int_env("MAX_CONCURRENT_RUNS", 4, lo=1, hi=32),
        timeout_scale=_float_env("TIMEOUT_SCALE", 1.0, lo=1.0, hi=6.0),
        curl_image=_env("CURL_IMAGE", "argustrace-curl:1.0"),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )


SETTINGS = load()
