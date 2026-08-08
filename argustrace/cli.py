import asyncio
import ipaddress
import json

import typer

from argustrace import __version__
from argustrace.plugins.options import OptionError
from argustrace.plugins.options import validate as validate_options
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


def _build_options(plugin: str, pairs: list[str]) -> dict:
    """Parse `name=value` pairs, then hand them to the shared validator.

    Coercion and bounds checking live in plugins/options.py so the CLI and the
    API agree on what a given value means and on which values are refused.
    """
    if not pairs:
        return {}

    raw: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise typer.BadParameter(f"expected name=value, got {pair!r}")
        raw[name] = value

    try:
        return validate_options(plugin, raw)
    except OptionError as e:
        raise typer.BadParameter(str(e)) from None


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
def version():
    """Print the installed ArgusTrace version."""
    print(__version__)


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
