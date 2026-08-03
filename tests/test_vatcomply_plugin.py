from argustrace.core.models import Status
from argustrace.plugins import vatcomply_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.vatcomply_plugin import VatComplyPlugin


async def test_invalid_entity_is_error_without_touching_docker():
    plugin = VatComplyPlugin()
    findings = await plugin.run("!!!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_run_invalid_input_detail_is_error_no_retry(monkeypatch):
    calls = 0

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        nonlocal calls
        calls += 1
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"detail": "INVALID_INPUT"}', stderr=b"", error=None)

    monkeypatch.setattr(vatcomply_plugin, "run_hardened", fake_run_hardened)

    plugin = VatComplyPlugin()
    findings = await plugin.run("FR40303265045")

    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]
    assert calls == 1  # a real format error shouldn't be retried


async def test_run_retries_on_transient_vies_error_then_succeeds(monkeypatch):
    calls = 0

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        nonlocal calls
        calls += 1
        if calls < 3:
            return DockerRunResult(ok=True, returncode=0, stdout=b'{"detail": "MS_MAX_CONCURRENT_REQ"}', stderr=b"", error=None)
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"valid": true, "name": "ACME", "country_code": "FR"}', stderr=b"", error=None)

    async def instant_sleep(_seconds):
        pass

    monkeypatch.setattr(vatcomply_plugin, "run_hardened", fake_run_hardened)
    monkeypatch.setattr(vatcomply_plugin.asyncio, "sleep", instant_sleep)

    plugin = VatComplyPlugin()
    findings = await plugin.run("FR40303265045")

    assert findings[0].status == Status.FOUND
    assert calls == 3


async def test_run_gives_up_after_max_attempts_of_transient_errors(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"detail": "MS_MAX_CONCURRENT_REQ"}', stderr=b"", error=None)

    async def instant_sleep(_seconds):
        pass

    monkeypatch.setattr(vatcomply_plugin, "run_hardened", fake_run_hardened)
    monkeypatch.setattr(vatcomply_plugin.asyncio, "sleep", instant_sleep)

    plugin = VatComplyPlugin()
    findings = await plugin.run("FR40303265045")

    assert findings[0].status == Status.ERROR
    assert "EU VIES system error" in findings[0].evidence["reason"]
    assert "invalid entity" not in findings[0].evidence["reason"]


def test_parse_response_invalid_vat_is_not_found():
    plugin = VatComplyPlugin()
    data = {"valid": False, "vat_number": "00000000000", "country_code": "FR", "name": "---", "address": "---"}

    finding = plugin._parse_response("FR00000000000", data)[0]

    assert finding.status == Status.NOT_FOUND


def test_parse_response_valid_vat_is_found():
    plugin = VatComplyPlugin()
    data = {
        "valid": True, "vat_number": "40303265045", "country_code": "FR",
        "name": "SA SODIMAS", "address": "11 RUE AMPERE\n26600 PONT DE L ISERE",
    }

    finding = plugin._parse_response("FR40303265045", data)[0]

    assert finding.status == Status.FOUND
    assert finding.evidence["name"] == "SA SODIMAS"
    assert finding.evidence["headline"] == "SA SODIMAS"
    assert finding.evidence["country_code"] == "FR"


async def test_run_normalizes_spaces_and_case(monkeypatch):
    captured = {}

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        captured["url"] = args[0]
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"valid": false}', stderr=b"", error=None)

    monkeypatch.setattr(vatcomply_plugin, "run_hardened", fake_run_hardened)

    plugin = VatComplyPlugin()
    await plugin.run("fr 40303265045")

    assert "FR40303265045" in captured["url"]


async def test_run_reports_docker_failure(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=1, stdout=b"", stderr=b"boom", error=None)

    async def instant_sleep(_seconds):
        pass

    monkeypatch.setattr(vatcomply_plugin, "run_hardened", fake_run_hardened)
    monkeypatch.setattr(vatcomply_plugin.asyncio, "sleep", instant_sleep)

    plugin = VatComplyPlugin()
    findings = await plugin.run("FR40303265045")

    assert findings[0].status == Status.ERROR
    assert "curl failed" in findings[0].evidence["reason"]
