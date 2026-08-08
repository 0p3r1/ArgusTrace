import secrets
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from argustrace import __version__, versioning
from argustrace.core.models import Finding
from argustrace.logging_setup import configure as configure_logging
from argustrace.logging_setup import get_logger
from argustrace.plugins.options import OptionError
from argustrace.plugins.options import validate as validate_options
from argustrace.plugins.registry import NATIVE_REPORT_GENERATORS, PLUGINS, TOOL_FAMILIES
from argustrace.settings import SETTINGS

configure_logging()
logger = get_logger(__name__)

TOKEN_HEADER = "X-ArgusTrace-Token"  # noqa: S105 — a header name, not a secret


def require_token(x_argustrace_token: str = Header(default="")) -> None:
    """Gate every endpoint behind a shared token, when one is configured.

    Reaching this API means being able to run containers and make the host
    fetch arbitrary URLs, so it is not something to leave open on a reachable
    interface. No token is required by default because the intended use is
    loopback-only and a mandatory secret would just be friction; `argustrace
    serve` is what refuses to bind a non-loopback address without one.
    """
    if not SETTINGS.api_token:
        return
    if not secrets.compare_digest(x_argustrace_token, SETTINGS.api_token):
        logger.warning("rejected a request with a missing or invalid %s", TOKEN_HEADER)
        raise HTTPException(status_code=401, detail=f"missing or invalid {TOKEN_HEADER}")


app = FastAPI(title="ArgusTrace", version=__version__, dependencies=[Depends(require_token)])

# Lets the Vite dev server (a different origin) call this API. Methods and
# headers are enumerated rather than "*" so the allowance stays as narrow as
# what the frontend actually uses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", TOKEN_HEADER],
)


class InvestigateRequest(BaseModel):
    entity: str
    plugin: str = "mock"
    options: dict | None = None


class ToolVariant(BaseModel):
    key: str
    variant_label: str
    speed: str
    fast: bool


class ToolOption(BaseModel):
    name: str
    flag: str
    type: Literal["int", "str", "bool", "enum", "enum_multi", "secret"]
    required: bool = False
    default: object | None = None
    min: int | None = None
    max: int | None = None
    choices: list[str] | None = None
    description: str


class VersionInfo(BaseModel):
    status: Literal["current", "behind", "outdated", "unknown", "not_applicable"]
    pinned: str | None = None
    latest: str | None = None
    checked_at: datetime | None = None
    detail: str | None = None


class ToolExample(BaseModel):
    label: str
    entity: str


class NativeReport(BaseModel):
    format: str
    label: str
    kind: Literal["download", "link", "info"]
    available: bool
    note: str
    mime: str | None = None
    url_template: str | None = None


class ToolFamily(BaseModel):
    family: str
    label: str
    entity_type: str
    description: str
    variants: list[ToolVariant]
    options: list[ToolOption] = []
    native_reports: list[NativeReport] = []
    version: VersionInfo
    repo_url: str | None = None
    docs_url: str | None = None
    examples: list[ToolExample] = []
    hidden: bool = False
    source_kind: Literal["api", "cli_tool"] = "cli_tool"
    requires_key: bool = False
    key_note: str | None = None


def _version_info(family: str, version_check: dict) -> VersionInfo:
    if version_check["method"] == "none":
        return VersionInfo(status="not_applicable")
    result = versioning.cached(family)
    if result is None:
        return VersionInfo(status="unknown")
    return VersionInfo(
        status=result.status.value,
        pinned=result.pinned,
        latest=result.latest,
        checked_at=result.checked_at,
        detail=result.detail,
    )


def _tool_family(family: str, info: dict) -> ToolFamily:
    return ToolFamily(
        family=family,
        label=info["label"],
        entity_type=info["entity_type"],
        description=info["description"],
        variants=[
            ToolVariant(key=key, **variant)
            for key, variant in info["variants"].items()
        ],
        options=[ToolOption(**opt) for opt in info.get("options", [])],
        native_reports=[NativeReport(**r) for r in info.get("native_reports", [])],
        version=_version_info(family, info.get("version_check", {"method": "none"})),
        repo_url=info.get("repo_url"),
        docs_url=info.get("docs_url"),
        examples=[ToolExample(**ex) for ex in info.get("examples", [])],
        hidden=info.get("hidden", False),
        source_kind=info.get("source_kind", "cli_tool"),
        requires_key=info.get("requires_key", False),
        key_note=info.get("key_note"),
    )


@app.get("/api/version")
def get_version() -> dict[str, str]:
    return {"version": __version__}


@app.get("/api/plugins")
def list_plugins() -> list[ToolFamily]:
    # A malformed family is skipped rather than allowed to take the whole
    # catalog down: this used to index required keys directly, so one bad
    # entry returned a 500 for all thirteen tools. test_registry_consistency
    # keeps a broken one from shipping; this is the second line of defence.
    families = []
    for family, info in TOOL_FAMILIES.items():
        try:
            families.append(_tool_family(family, info))
        except Exception:
            logger.exception("skipping malformed tool family %r", family)
    return families


@app.post("/api/tools/{family}/version-check")
async def check_tool_version(family: str) -> VersionInfo:
    info = TOOL_FAMILIES.get(family)
    if info is None:
        raise HTTPException(status_code=404, detail=f"unknown tool family: {family}")
    result = await versioning.check(family, info["version_check"])
    return VersionInfo(
        status=result.status.value,
        pinned=result.pinned,
        latest=result.latest,
        checked_at=result.checked_at,
        detail=result.detail,
    )


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest) -> list[Finding]:
    selected = PLUGINS.get(req.plugin)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"unknown plugin: {req.plugin}")

    # Checked here rather than inside each plugin so a bad value is refused
    # with a message instead of being silently clamped or dropped.
    try:
        options = validate_options(req.plugin, req.options)
    except OptionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return await selected.run(req.entity, options or None)


@app.get("/api/tools/{family}/report")
async def get_native_report(family: str, entity: str, format: str, plugin: str | None = None) -> Response:
    info = TOOL_FAMILIES.get(family)
    if info is None:
        raise HTTPException(status_code=404, detail=f"unknown tool family: {family}")
    if plugin is not None and plugin not in PLUGINS:
        raise HTTPException(status_code=404, detail=f"unknown plugin: {plugin}")

    entry = next(
        (r for r in info.get("native_reports", []) if r["format"] == format and r["kind"] == "download"),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no downloadable {format!r} report for {family!r}")
    if not entry["available"]:
        raise HTTPException(status_code=400, detail=f"{family!r} {format!r} report is not available: {entry['note']}")

    generator = NATIVE_REPORT_GENERATORS.get(family)
    if generator is None:
        raise HTTPException(status_code=500, detail=f"{family!r} has no report generator wired up")

    # On-demand only — this re-runs the tool fresh, nothing is cached.
    # `plugin` is the exact variant the caller's results came from (e.g.
    # "theharvester-broad" vs "theharvester") — some generators use it to
    # match the report to the scan actually run instead of always
    # defaulting to the fast variant's sources.
    try:
        content = await generator(entity, format, plugin)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return Response(
        content=content,
        media_type=entry["mime"],
        headers={"Content-Disposition": f'attachment; filename="{family}_{entity}.{format}"'},
    )
