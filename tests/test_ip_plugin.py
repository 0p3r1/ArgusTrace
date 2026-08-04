import json

from argustrace.core.models import Status
from argustrace.plugins import ip_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.ip_plugin import IPPlugin


async def test_invalid_format_returns_error_without_touching_docker():
    plugin = IPPlugin()
    findings = await plugin.run("not-an-ip")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "not a valid IPv4/IPv6" in findings[0].evidence["reason"]


async def test_private_ip_returns_error_without_touching_docker():
    plugin = IPPlugin()
    findings = await plugin.run("192.168.1.1")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "not a public, routable" in findings[0].evidence["reason"]


async def test_loopback_and_link_local_are_also_rejected():
    plugin = IPPlugin()
    for entity in ["127.0.0.1", "::1", "169.254.1.1"]:
        findings = await plugin.run(entity)
        assert findings[0].status == Status.ERROR, entity


def test_parse_rdap_extracts_network_info_and_org_name():
    plugin = IPPlugin()
    stdout = json.dumps({
        "name": "GOOGLE-IPV6",
        "handle": "NET6-2001-4860-1",
        "startAddress": "2001:4860::",
        "endAddress": "2001:4860:ffff::",
        "status": ["active"],
        "country": "US",
        "port43": "whois.arin.net",
        "entities": [
            {"vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Google LLC"]]]},
        ],
    })

    finding = plugin._parse_rdap("2001:4860:4860::8888", stdout)

    assert finding.status == Status.FOUND
    assert finding.evidence["network_name"] == "GOOGLE-IPV6"
    assert finding.evidence["organization"] == "Google LLC"
    assert finding.evidence["range"] == "2001:4860:: - 2001:4860:ffff::"
    assert finding.evidence["headline"] == "Google LLC · US"


def test_parse_rdap_headline_falls_back_to_network_name_without_org():
    plugin = IPPlugin()
    stdout = json.dumps({"name": "PRIVATE-ADDRESS-CBLK", "status": ["reserved"]})

    finding = plugin._parse_rdap("192.0.2.1", stdout)

    assert finding.evidence["headline"] == "PRIVATE-ADDRESS-CBLK"


def test_parse_rdap_empty_body_is_error():
    # _parse_rdap is only reached once _rdap() already confirmed a 2xx
    # status — an empty body at that point is an anomaly, not a genuine
    # "no record" (that's now decided by the real HTTP status in _rdap()).
    plugin = IPPlugin()
    finding = plugin._parse_rdap("8.8.8.8", "")
    assert finding.status == Status.ERROR


def test_parse_rdap_non_json_is_error():
    plugin = IPPlugin()
    finding = plugin._parse_rdap("8.8.8.8", "<html>not json</html>")
    assert finding.status == Status.ERROR


def test_parse_geolocation_success():
    plugin = IPPlugin()
    stdout = json.dumps({
        "status": "success", "country": "Australia", "regionName": "Queensland",
        "city": "South Brisbane", "isp": "Cloudflare, Inc", "org": "APNIC and Cloudflare",
        "as": "AS13335 Cloudflare, Inc.", "lat": -27.4766, "lon": 153.0166,
    })

    finding = plugin._parse_geolocation("1.1.1.1", stdout)

    assert finding.status == Status.FOUND
    assert finding.evidence["country"] == "Australia"
    assert finding.evidence["coordinates"] == "-27.4766,153.0166"
    assert finding.evidence["headline"] == "South Brisbane, Queensland, Australia"


def test_parse_geolocation_failure_is_error():
    plugin = IPPlugin()
    stdout = json.dumps({"status": "fail", "message": "private range", "query": "192.168.1.1"})

    finding = plugin._parse_geolocation("192.168.1.1", stdout)

    assert finding.status == Status.ERROR
    assert finding.evidence["reason"] == "private range"


def test_resolve_sources_defaults_to_both():
    plugin = IPPlugin()
    assert plugin._resolve_sources({}) == ["rdap", "geolocation"]


def test_resolve_sources_filters_to_known_values():
    plugin = IPPlugin()
    assert plugin._resolve_sources({"sources": ["rdap", "bogus"]}) == ["rdap"]


def test_resolve_sources_falls_back_when_all_invalid():
    plugin = IPPlugin()
    assert plugin._resolve_sources({"sources": ["bogus"]}) == ["rdap", "geolocation"]


async def _instant_sleep(_seconds):
    pass


async def test_rdap_real_404_is_not_found(monkeypatch):
    # A genuine "no RDAP record" is an honest 404 with an empty body —
    # curl exits 0 either way, so the HTTP status (not just body emptiness)
    # is what must distinguish this from a transient failure below.
    monkeypatch.setattr(ip_plugin.asyncio, "sleep", _instant_sleep)

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b"\n404", stderr=b"", error=None)

    monkeypatch.setattr(ip_plugin, "run_hardened", fake_run_hardened)

    plugin = IPPlugin()
    finding = await plugin._rdap("8.8.8.8")

    assert finding.status == Status.NOT_FOUND


async def test_rdap_transient_5xx_with_empty_body_is_error_not_not_found(monkeypatch):
    # Verified live: rdap.org can return an empty body with curl exit 0 on
    # a transient upstream error — this used to be indistinguishable from
    # a real 404 and silently became NOT_FOUND. Retries are exhausted here
    # (every attempt returns 500), so it must end as ERROR.
    monkeypatch.setattr(ip_plugin.asyncio, "sleep", _instant_sleep)

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b"\n500", stderr=b"", error=None)

    monkeypatch.setattr(ip_plugin, "run_hardened", fake_run_hardened)

    plugin = IPPlugin()
    finding = await plugin._rdap("8.8.8.8")

    assert finding.status == Status.ERROR
    assert "HTTP 500" in finding.evidence["reason"]


async def test_rdap_succeeds_after_transient_failure_retry(monkeypatch):
    monkeypatch.setattr(ip_plugin.asyncio, "sleep", _instant_sleep)
    attempts = []

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        attempts.append(1)
        if len(attempts) == 1:
            return DockerRunResult(ok=True, returncode=0, stdout=b"\n503", stderr=b"", error=None)
        body = json.dumps({"name": "GOOGLE"}).encode()
        return DockerRunResult(ok=True, returncode=0, stdout=body + b"\n200", stderr=b"", error=None)

    monkeypatch.setattr(ip_plugin, "run_hardened", fake_run_hardened)

    plugin = IPPlugin()
    finding = await plugin._rdap("8.8.8.8")

    assert len(attempts) == 2
    assert finding.status == Status.FOUND
    assert finding.evidence["network_name"] == "GOOGLE"


async def test_rdap_docker_failure_is_error(monkeypatch):
    monkeypatch.setattr(ip_plugin.asyncio, "sleep", _instant_sleep)

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=False, returncode=None, stdout=b"", stderr=b"", error="docker not available")

    monkeypatch.setattr(ip_plugin, "run_hardened", fake_run_hardened)

    plugin = IPPlugin()
    finding = await plugin._rdap("8.8.8.8")

    assert finding.status == Status.ERROR
    assert "docker not available" in finding.evidence["reason"]


async def test_geolocation_docker_failure_is_error(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=False, returncode=None, stdout=b"", stderr=b"", error="docker not available")

    monkeypatch.setattr(ip_plugin, "run_hardened", fake_run_hardened)

    plugin = IPPlugin()
    finding = await plugin._geolocation("8.8.8.8")

    assert finding.status == Status.ERROR
    assert "docker not available" in finding.evidence["reason"]
