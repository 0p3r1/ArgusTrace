import json

from argustrace.core.models import Status
from argustrace.plugins import wayback_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.wayback_plugin import WaybackPlugin


async def test_invalid_entity_is_error_without_touching_docker():
    plugin = WaybackPlugin()
    findings = await plugin.run("not a domain!!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_rows_empty_is_not_found():
    plugin = WaybackPlugin()
    findings = plugin._parse_rows("nonexistent.example", [])

    assert findings[0].status == Status.NOT_FOUND


def test_parse_rows_groups_by_host():
    plugin = WaybackPlugin()
    rows = [
        ["original", "timestamp", "statuscode"],
        ["http://www.example.com/", "20000304021913", "200"],
        ["http://www.example.com/about", "20200101000000", "200"],
        ["http://api.example.com/v1", "20150601000000", "200"],
    ]

    findings = plugin._parse_rows("example.com", rows)

    sources = {f.source for f in findings}
    assert sources == {"wayback:www.example.com", "wayback:api.example.com"}
    www_finding = next(f for f in findings if f.source == "wayback:www.example.com")
    assert www_finding.status == Status.FOUND
    assert www_finding.evidence["snapshot_count"] == 2
    assert www_finding.evidence["first_archived"] == "2000-03-04"
    assert www_finding.evidence["last_archived"] == "2020-01-01"


def test_format_timestamp():
    plugin = WaybackPlugin()
    assert plugin._format_timestamp("20240510074012") == "2024-05-10"


async def test_run_reports_docker_failure(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=1, stdout=b"", stderr=b"boom", error=None)

    monkeypatch.setattr(wayback_plugin, "run_hardened", fake_run_hardened)

    plugin = WaybackPlugin()
    findings = await plugin.run("example.com")

    assert findings[0].status == Status.ERROR
    assert "curl failed" in findings[0].evidence["reason"]


async def test_run_parses_real_shaped_output(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        stdout = json.dumps([
            ["original", "timestamp", "statuscode"],
            ["http://example.com/", "20100101000000", "200"],
        ]).encode()
        return DockerRunResult(ok=True, returncode=0, stdout=stdout, stderr=b"", error=None)

    monkeypatch.setattr(wayback_plugin, "run_hardened", fake_run_hardened)

    plugin = WaybackPlugin()
    findings = await plugin.run("example.com")

    assert findings[0].status == Status.FOUND
    assert findings[0].evidence["host"] == "example.com"
