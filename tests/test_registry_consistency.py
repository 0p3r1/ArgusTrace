"""Consistency checks over the registry as pure data — no Docker, no network.

These exist because several ways of breaking the app are invisible to the
per-plugin tests: they all pass while `/api/plugins` returns a 500 for every
tool, or a report button 500s, or a pinned version silently disagrees with
what the Dockerfile actually installs. Each test below corresponds to a real
failure mode that was previously guarded only by a code comment.
"""

import re
from pathlib import Path

import pytest

from argustrace.api import list_plugins
from argustrace.plugins.registry import NATIVE_REPORT_GENERATORS, PLUGINS, TOOL_FAMILIES

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_every_variant_key_is_a_registered_plugin():
    for family, info in TOOL_FAMILIES.items():
        for key in info["variants"]:
            assert key in PLUGINS, f"{family!r} declares variant {key!r}, absent from PLUGINS"


def test_every_registered_plugin_is_reachable_from_some_family():
    """A plugin missing from TOOL_FAMILIES runs from the CLI but is invisible
    in the web catalog — a silent half-registration."""
    declared = {key for info in TOOL_FAMILIES.values() for key in info["variants"]}
    assert set(PLUGINS) == declared


def test_native_report_generators_are_real_families():
    assert set(NATIVE_REPORT_GENERATORS) <= set(TOOL_FAMILIES)


def test_available_downloadable_reports_have_a_generator():
    """api.py raises a 500 when a family advertises a downloadable report it
    has no generator for — the UI shows the button, the click fails."""
    for family, info in TOOL_FAMILIES.items():
        downloadable = [
            r for r in info.get("native_reports", [])
            if r["kind"] == "download" and r["available"]
        ]
        if downloadable:
            assert family in NATIVE_REPORT_GENERATORS, (
                f"{family!r} advertises {[r['format'] for r in downloadable]} "
                "as downloadable but has no generator"
            )


def test_link_reports_have_a_url_template():
    for family, info in TOOL_FAMILIES.items():
        for report in info.get("native_reports", []):
            if report["kind"] == "link":
                assert report.get("url_template"), f"{family!r} link report has no url_template"


def test_every_family_serializes(monkeypatch):
    """`list_plugins` indexes required keys directly, so one family missing a
    key 500s the whole catalog for every tool, not just its own."""
    families = list_plugins()
    assert len(families) == len(TOOL_FAMILIES)


# --- pinned versions -------------------------------------------------------
# The Dockerfile is the source of truth for what actually gets installed;
# registry.py's `pinned_version` is what the UI reports and what the upstream
# version check compares against. They must agree, and until now nothing
# enforced that beyond a comment. Sherlock and Maigret are pinned by upstream
# image digest with no Dockerfile of ours, so there is nothing to grep — their
# pinned_version stays a manual annotation.
# Each entry extracts the version the Dockerfile actually installs. These are
# deliberately anchored to the install directive rather than searching for the
# version as a bare substring: several Dockerfiles mention other version
# numbers in prose (holehe's comment explains what happens "the day upstream
# ships 1.62"), and a substring match happily finds those, passing while the
# real pin disagrees.
FAMILY_PINS = {
    "holehe": ("docker/holehe/Dockerfile", r"holehe==([0-9][^\s\"']*)"),
    "ignorant": ("docker/ignorant/Dockerfile", r"ignorant==([0-9][^\s\"']*)"),
    "theharvester": ("docker/theharvester/Dockerfile", r"--branch\s+([0-9][^\s\"']*)"),
    "exif": ("docker/exiftool/Dockerfile", r"--branch\s+([0-9][^\s\"']*)"),
}


@pytest.mark.parametrize(("family", "spec"), sorted(FAMILY_PINS.items()))
def test_pinned_version_matches_what_the_dockerfile_installs(family, spec):
    dockerfile, pattern = spec
    pinned = TOOL_FAMILIES[family]["version_check"].get("pinned_version")
    if pinned is None:
        pytest.skip(f"{family} does not declare a pinned_version")

    # Strip comments so prose can never satisfy the match.
    content = (REPO_ROOT / dockerfile).read_text()
    directives = "\n".join(
        line for line in content.splitlines() if not line.lstrip().startswith("#")
    )

    match = re.search(pattern, directives)
    assert match, f"could not find an install directive matching {pattern!r} in {dockerfile}"
    assert match.group(1) == pinned, (
        f"registry pins {family} at {pinned!r} but {dockerfile} installs "
        f"{match.group(1)!r} — bump both together"
    )


# --- timeout layering ------------------------------------------------------
# The shared curl image sets its own `--max-time`, and the plugin sets the
# outer `docker run` timeout. The outer one must be comfortably larger: if it
# fires first the container is killed mid-request, which loses curl's own
# clean error (and, before the runner learned to reap them, leaked the
# container). Margin covers container startup.
CURL_STARTUP_MARGIN_S = 5


def _curl_image_max_time() -> int:
    content = (REPO_ROOT / "docker/curl/Dockerfile").read_text()
    match = re.search(r'"--max-time",\s*"(\d+)"', content)
    assert match, "could not find --max-time in docker/curl/Dockerfile"
    return int(match.group(1))


def _curl_backed_plugin_modules():
    """Plugin modules whose requests run through the shared curl image.

    Detected two ways: a module that calls `fetch_json` (which defaults to
    that image), or one still declaring the image directly. Both forms are
    picked up so the check keeps holding as plugins move onto the helper.
    """
    import importlib
    import pkgutil

    import argustrace.plugins as plugins_pkg
    from argustrace.plugins import _common

    for module_info in pkgutil.iter_modules(plugins_pkg.__path__):
        module = importlib.import_module(f"argustrace.plugins.{module_info.name}")
        if module is _common:
            continue
        uses_helper = getattr(module, "fetch_json", None) is _common.fetch_json
        image = getattr(module, "IMAGE", "")
        declares_image = isinstance(image, str) and image.startswith("argustrace-curl")
        if uses_helper or declares_image:
            yield module


def test_curl_backed_plugins_outlast_the_container_own_timeout():
    max_time = _curl_image_max_time()
    modules = list(_curl_backed_plugin_modules())
    assert modules, "expected at least one plugin using the shared curl image"

    for module in modules:
        run_timeout = getattr(module, "RUN_TIMEOUT_S", None)
        assert run_timeout is not None, f"{module.__name__} has no RUN_TIMEOUT_S"
        assert run_timeout >= max_time + CURL_STARTUP_MARGIN_S, (
            f"{module.__name__} allows {run_timeout}s but the curl image gives up at "
            f"{max_time}s — the outer timeout fires first and the container is killed "
            "mid-request instead of curl returning its own error"
        )
