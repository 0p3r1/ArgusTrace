import asyncio
import json

import typer

from argustrace.plugins.holehe_plugin import HolehePlugin
from argustrace.plugins.ignorant_plugin import IgnorantPlugin
from argustrace.plugins.mock_plugin import MockPlugin
from argustrace.plugins.sherlock_plugin import SherlockPlugin

app = typer.Typer()

PLUGINS = {
    "mock": MockPlugin(),
    "sherlock": SherlockPlugin(),        # fast: curated site list (~10s)
    "sherlock-full": SherlockPlugin(sites=None),  # slow: full ~400+ site scan
    "holehe": HolehePlugin(),
    "ignorant": IgnorantPlugin(),
}


@app.command()
def investigate(entity: str, plugin: str = "mock"):
    selected = PLUGINS[plugin]
    findings = asyncio.run(selected.run(entity))
    print(json.dumps([f.model_dump(mode="json") for f in findings], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
