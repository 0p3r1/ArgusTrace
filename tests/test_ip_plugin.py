import json

from argustrace.core.models import Status
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


def test_parse_rdap_empty_body_is_not_found():
    plugin = IPPlugin()
    finding = plugin._parse_rdap("8.8.8.8", "")
    assert finding.status == Status.NOT_FOUND


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
