from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from argustrace.core.models import Finding
from argustrace.plugins.registry import PLUGINS

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


@app.get("/api/plugins")
def list_plugins() -> list[str]:
    return list(PLUGINS.keys())


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest) -> list[Finding]:
    selected = PLUGINS.get(req.plugin)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"unknown plugin: {req.plugin}")
    return await selected.run(req.entity)
