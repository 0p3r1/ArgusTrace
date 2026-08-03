from argustrace.core.models import Status
from argustrace.plugins import name_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.name_plugin import NamePlugin


async def test_invalid_entity_is_error_without_touching_docker():
    plugin = NamePlugin()
    findings = await plugin.run("Jean Pierre")  # multi-word, not a single first name

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_digits_are_rejected():
    plugin = NamePlugin()
    findings = await plugin.run("Jean123")

    assert findings[0].status == Status.ERROR


def test_build_finding_all_signals_present():
    plugin = NamePlugin()
    gender_data = {"count": 1000, "name": "jean", "gender": "male", "probability": 0.62}
    age_data = {"count": 500, "name": "jean", "age": 64}
    nationality_data = {"count": 800, "name": "jean", "country": [
        {"country_id": "FR", "probability": 0.256},
        {"country_id": "US", "probability": 0.068},
    ]}

    finding = plugin._build_finding("jean", gender_data, age_data, nationality_data, [])

    assert finding.status == Status.FOUND
    assert finding.evidence["gender"] == "male"
    assert finding.evidence["estimated_age"] == 64
    assert finding.evidence["likely_countries"][0] == "FR (26%)"
    assert "male (62%)" in finding.evidence["headline"]
    assert "~64 y/o" in finding.evidence["headline"]


def test_build_finding_all_empty_is_not_found():
    plugin = NamePlugin()
    gender_data = {"count": 0, "name": "xyz", "gender": None, "probability": 0.0}
    age_data = {"count": 0, "name": "xyz", "age": None}
    nationality_data = {"count": 0, "name": "xyz", "country": []}

    finding = plugin._build_finding("xyz", gender_data, age_data, nationality_data, [])

    assert finding.status == Status.NOT_FOUND


def test_build_finding_partial_errors_still_found_if_some_signal():
    plugin = NamePlugin()
    gender_data = {"count": 1000, "name": "jean", "gender": "male", "probability": 0.62}

    finding = plugin._build_finding("jean", gender_data, None, None, ["agify: timeout", "nationalize: timeout"])

    assert finding.status == Status.FOUND
    assert finding.evidence["gender"] == "male"
    assert "agify: timeout" in finding.evidence["reason"]


def test_build_finding_all_errors_is_error():
    plugin = NamePlugin()

    finding = plugin._build_finding("jean", None, None, None, ["genderize: down", "agify: down", "nationalize: down"])

    assert finding.status == Status.ERROR


async def test_run_all_three_sources_fail(monkeypatch):
    async def fake_fetch(self, url, label):
        return f"{label}: connection refused"

    monkeypatch.setattr(name_plugin.NamePlugin, "_fetch", fake_fetch)

    plugin = name_plugin.NamePlugin()
    findings = await plugin.run("jean")

    assert findings[0].status == Status.ERROR
    assert "connection refused" in findings[0].evidence["reason"]


async def test_fetch_treats_valid_json_error_body_as_a_failure_not_data(monkeypatch):
    # Verified against the real API: hitting the daily rate limit doesn't
    # fail curl or break JSON parsing — it's a 200-shaped, valid JSON body
    # {"error": "Request limit reached"}. Without an explicit check this
    # silently reads as "responded with no data", producing a false
    # NOT_FOUND instead of an ERROR for a condition we never actually verified.
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"error": "Request limit reached"}', stderr=b"", error=None)

    monkeypatch.setattr(name_plugin, "run_hardened", fake_run_hardened)

    plugin = NamePlugin()
    findings = await plugin.run("jean")

    assert findings[0].status == Status.ERROR
    assert "Request limit reached" in findings[0].evidence["reason"]
