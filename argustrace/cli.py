import asyncio
import ipaddress
import json

import typer

from argustrace.plugins.registry import PLUGINS, TOOL_FAMILIES
from argustrace.settings import SETTINGS

app = typer.Typer()


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def _family_for_plugin(plugin: str) -> dict | None:
    for info in TOOL_FAMILIES.values():
        if plugin in info["variants"]:
            return info
    return None


def _coerce_option(name: str, raw: str, spec: dict):
    if spec["type"] == "int":
        try:
            return int(raw)
        except ValueError:
            raise typer.BadParameter(f"--option {name}: expected an integer, got {raw!r}") from None
    if spec["type"] == "bool":
        return raw.strip().lower() not in ("", "0", "false", "no")
    if spec["type"] == "enum_multi":
        return [v.strip() for v in raw.split(",") if v.strip()]
    return raw


def _build_options(plugin: str, pairs: list[str]) -> dict:
    if not pairs:
        return {}

    family = _family_for_plugin(plugin)
    specs = {opt["name"]: opt for opt in family["options"]} if family else {}

    options = {}
    for pair in pairs:
        name, sep, raw = pair.partition("=")
        if not sep:
            raise typer.BadParameter(f"expected name=value, got {pair!r}")
        spec = specs.get(name)
        if spec is None:
            known = ", ".join(specs) or "(none)"
            raise typer.BadParameter(f"unknown option {name!r} for plugin {plugin!r} — known options: {known}")
        options[name] = _coerce_option(name, raw, spec)
    return options


@app.command()
def investigate(
    entity: str,
    plugin: str = "mock",
    option: list[str] = typer.Option(
        [], "--option", "-o",
        help="Tool option as name=value, repeatable (e.g. -o timeout=20 -o nsfw=true). "
             "See `argustrace options <plugin>` for what's available.",
    ),
):
    if plugin not in PLUGINS:
        raise typer.BadParameter(f"unknown plugin {plugin!r} — see `argustrace options` for the list of families")

    options = _build_options(plugin, option)
    selected = PLUGINS[plugin]
    findings = asyncio.run(selected.run(entity, options or None))
    print(json.dumps([f.model_dump(mode="json") for f in findings], indent=2, ensure_ascii=False))


@app.command()
def options(plugin: str = typer.Argument(None, help="Plugin/variant key, e.g. 'maigret'. Omit to list all families.")):
    if plugin is None:
        for family, info in TOOL_FAMILIES.items():
            if info.get("hidden"):
                continue
            variants = ", ".join(info["variants"])
            print(f"{family}: {info['label']} ({variants})")
        return

    family = _family_for_plugin(plugin)
    if family is None:
        raise typer.BadParameter(f"unknown plugin {plugin!r}")
    if not family["options"]:
        print(f"{plugin} has no configurable options beyond entity and plugin variant.")
        return
    for opt in family["options"]:
        print(f"{opt['name']} ({opt['type']}, flag {opt['flag']}, default={opt.get('default')!r})")
        print(f"    {opt['description']}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind. Loopback unless a token is set."),
    port: int = typer.Option(8000, help="Port to listen on."),
):
    """Run the web API.

    Defaults to loopback because reaching this API means being able to run
    containers and make the host fetch arbitrary URLs. Binding it anywhere
    else without ARGUSTRACE_API_TOKEN is refused here rather than left as a
    documentation convention.
    """
    if not _is_loopback(host) and not SETTINGS.api_token:
        raise typer.BadParameter(
            f"refusing to bind {host} without authentication: anyone who can reach this port "
            "could run containers and make this host fetch arbitrary URLs. Set "
            "ARGUSTRACE_API_TOKEN to a shared secret, or bind 127.0.0.1.",
            param_hint="--host",
        )

    import uvicorn

    uvicorn.run("argustrace.api:app", host=host, port=port)


if __name__ == "__main__":
    app()
