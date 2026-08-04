import json

from argustrace.core.models import Status
from argustrace.plugins import ignorant_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.ignorant_plugin import IgnorantPlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = IgnorantPlugin()
    findings = await plugin.run("not a phone number")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_rows_maps_ratelimit_and_exists_onto_status():
    plugin = IgnorantPlugin()
    rows = [
        {"name": "amazon", "domain": "amazon.com", "method": "login", "rateLimit": False, "exists": False},
        {"name": "instagram", "domain": "instagram.com", "method": "other", "rateLimit": False, "exists": True},
        {"name": "snapchat", "domain": "snapchat.com", "method": "register", "rateLimit": True, "exists": False},
    ]

    findings = plugin._parse_rows("+16502530000", rows)

    by_source = {f.source: f for f in findings}
    assert len(findings) == 3
    assert by_source["ignorant:amazon"].status == Status.NOT_FOUND
    assert by_source["ignorant:instagram"].status == Status.FOUND
    # rateLimit=True takes priority over exists, regardless of its value.
    assert by_source["ignorant:snapchat"].status == Status.ERROR
    assert by_source["ignorant:instagram"].evidence["headline"] == "instagram.com · other"


def test_resolve_timeout_uses_default_when_absent():
    plugin = IgnorantPlugin()
    assert plugin._resolve_timeout({}) == 10


def test_resolve_timeout_uses_custom_value():
    plugin = IgnorantPlugin()
    assert plugin._resolve_timeout({"timeout": 20}) == 20


def test_resolve_timeout_clamps_out_of_range_value():
    plugin = IgnorantPlugin()
    assert plugin._resolve_timeout({"timeout": 999}) == 30
    assert plugin._resolve_timeout({"timeout": 1}) == 5


def test_resolve_timeout_ignores_invalid_type():
    plugin = IgnorantPlugin()
    assert plugin._resolve_timeout({"timeout": "not-a-number"}) == 10


async def test_run_reports_docker_failure(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=False, returncode=None, stdout=b"", stderr=b"", error="docker not available")

    monkeypatch.setattr(ignorant_plugin, "run_hardened", fake_run_hardened)

    plugin = IgnorantPlugin()
    findings = await plugin.run("+16502530000")

    assert findings[0].status == Status.ERROR
    assert "docker not available" in findings[0].evidence["reason"]


async def test_run_reports_nonzero_exit(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=1, stdout=b"", stderr=b"boom", error=None)

    monkeypatch.setattr(ignorant_plugin, "run_hardened", fake_run_hardened)

    plugin = IgnorantPlugin()
    findings = await plugin.run("+16502530000")

    assert findings[0].status == Status.ERROR
    assert "docker run failed" in findings[0].evidence["reason"]


async def test_run_reports_unparseable_json(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b"not json", stderr=b"", error=None)

    monkeypatch.setattr(ignorant_plugin, "run_hardened", fake_run_hardened)

    plugin = IgnorantPlugin()
    findings = await plugin.run("+16502530000")

    assert findings[0].status == Status.ERROR
    assert "no parseable JSON" in findings[0].evidence["reason"]


async def test_run_parses_real_shaped_output(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        stdout = json.dumps([
            {"name": "amazon", "domain": "amazon.com", "method": "login", "rateLimit": False, "exists": True},
        ]).encode()
        return DockerRunResult(ok=True, returncode=0, stdout=stdout, stderr=b"", error=None)

    monkeypatch.setattr(ignorant_plugin, "run_hardened", fake_run_hardened)

    plugin = IgnorantPlugin()
    findings = await plugin.run("+16502530000")

    assert findings[0].status == Status.FOUND
    assert findings[0].source == "ignorant:amazon"
