from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from argustrace import versioning
from argustrace.core.models import Finding
from argustrace.plugins.registry import PLUGINS, TOOL_FAMILIES

app = FastAPI(title="ArgusTrace")

# Dev-only: lets the Vite dev server (a different origin) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    type: Literal["int", "str", "bool", "enum", "enum_multi"]
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


class ToolFamily(BaseModel):
    family: str
    label: str
    entity_type: str
    description: str
    variants: list[ToolVariant]
    options: list[ToolOption] = []
    version: VersionInfo
    repo_url: str | None = None
    docs_url: str | None = None
    examples: list[ToolExample] = []
    hidden: bool = False


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


@app.get("/api/plugins")
def list_plugins() -> list[ToolFamily]:
    return [
        ToolFamily(
            family=family,
            label=info["label"],
            entity_type=info["entity_type"],
            description=info["description"],
            variants=[
                ToolVariant(key=key, **variant)
                for key, variant in info["variants"].items()
            ],
            options=[ToolOption(**opt) for opt in info["options"]],
            version=_version_info(family, info["version_check"]),
            repo_url=info["repo_url"],
            docs_url=info["docs_url"],
            examples=[ToolExample(**ex) for ex in info["examples"]],
            hidden=info.get("hidden", False),
        )
        for family, info in TOOL_FAMILIES.items()
    ]


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
    return await selected.run(req.entity, req.options)
