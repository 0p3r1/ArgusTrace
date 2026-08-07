from argustrace.core.models import Status
from argustrace.plugins import _common
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
    by_name = {f.evidence["name"]: f for f in findings}
    assert by_name["example.com"].evidence["headline"] == "Let's Encrypt · issued 2026-01-01"


def test_issuer_org_extracts_organization_from_a_raw_dn():
    plugin = CrtShPlugin()
    assert plugin._issuer_org("C=US, O=Let's Encrypt, CN=YR2") == "Let's Encrypt"


def test_issuer_org_falls_back_to_raw_string_without_an_o_component():
    plugin = CrtShPlugin()
    assert plugin._issuer_org("Some Free CA") == "Some Free CA"


def test_issuer_org_handles_missing_issuer():
    plugin = CrtShPlugin()
    assert plugin._issuer_org(None) is None


async def _instant_sleep(_seconds):
    pass


# The retry/parse ladder now lives in _common.fetch_json, so these patch there
# rather than in the plugin — the behaviour under test is unchanged.
async def test_run_reports_docker_failure(monkeypatch, fake_docker, docker_result):
    monkeypatch.setattr(_common.asyncio, "sleep", _instant_sleep)
    fake_docker(_common, docker_result(ok=False, returncode=None, error="docker not available"))

    findings = await CrtShPlugin().run("example.com")

    assert findings[0].status == Status.ERROR
    assert "docker not available" in findings[0].evidence["reason"]


async def test_run_treats_non_list_json_as_failure_not_a_crash(monkeypatch, fake_docker, docker_result):
    # crt.sh normally returns a JSON array, but under load can return a
    # JSON *object* instead (still valid JSON) — this used to crash
    # unhandled inside _parse_rows instead of retrying/failing cleanly.
    monkeypatch.setattr(_common.asyncio, "sleep", _instant_sleep)
    fake_docker(_common, docker_result(b'{"error": "too many requests"}'))

    findings = await CrtShPlugin().run("example.com")

    assert findings[0].status == Status.ERROR
    assert "unexpected JSON shape" in findings[0].evidence["reason"]


async def test_run_succeeds_after_one_retry(monkeypatch, fake_docker, docker_result):
    monkeypatch.setattr(_common.asyncio, "sleep", _instant_sleep)
    calls = fake_docker(
        _common,
        docker_result(b"", returncode=1, stderr=b"502 Bad Gateway"),
        docker_result(b"[]"),
    )

    findings = await CrtShPlugin().run("example.com")

    assert len(calls) == 2
    assert findings[0].status == Status.NOT_FOUND
