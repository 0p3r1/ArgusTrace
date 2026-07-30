from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ToolVariant(BaseModel):
    key: str
    variant_label: str
    speed: str


class ToolFamily(BaseModel):
    family: str
    label: str
    entity_type: str
    description: str
    variants: list[ToolVariant]


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
        )
        for family, info in TOOL_FAMILIES.items()
    ]


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest) -> list[Finding]:
    selected = PLUGINS.get(req.plugin)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"unknown plugin: {req.plugin}")
    return await selected.run(req.entity)
