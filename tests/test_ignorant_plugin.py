from argustrace.core.models import Status
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
