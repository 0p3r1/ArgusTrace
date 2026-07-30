from argustrace.core.models import Status
from argustrace.plugins.crtsh_plugin import CrtShPlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = CrtShPlugin()
    findings = await plugin.run("not a domain!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_empty_response_is_not_found():
    plugin = CrtShPlugin()
    findings = plugin._parse_rows("nonexistent-domain.example", [])

    assert len(findings) == 1
    assert findings[0].status == Status.NOT_FOUND


def test_parse_rows_dedupes_multi_san_certificates():
    plugin = CrtShPlugin()
    rows = [
        {
            "id": 1,
            "name_value": "*.example.com\nexample.com",
            "issuer_name": "Let's Encrypt",
            "not_before": "2026-01-01",
            "not_after": "2026-04-01",
        },
        {
            # A reissue of the same cert for the same name should not duplicate.
            "id": 2,
            "name_value": "example.com",
            "issuer_name": "Let's Encrypt",
            "not_before": "2026-02-01",
            "not_after": "2026-05-01",
        },
        {
            "id": 3,
            "name_value": "api.example.com",
            "issuer_name": "Let's Encrypt",
            "not_before": "2026-01-01",
            "not_after": "2026-04-01",
        },
    ]

    findings = plugin._parse_rows("example.com", rows)

    names = {f.evidence["name"] for f in findings}
    assert names == {"*.example.com", "example.com", "api.example.com"}
    assert all(f.status == Status.FOUND for f in findings)
