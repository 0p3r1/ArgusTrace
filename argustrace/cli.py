import asyncio
import json

import typer

from argustrace.plugins.registry import PLUGINS

app = typer.Typer()


@app.command()
def investigate(entity: str, plugin: str = "mock"):
    selected = PLUGINS[plugin]
    findings = asyncio.run(selected.run(entity))
    print(json.dumps([f.model_dump(mode="json") for f in findings], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
