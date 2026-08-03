import json

from argustrace.core.models import Status
from argustrace.plugins import toutatis_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.toutatis_plugin import ToutatisPlugin


async def test_invalid_entity_is_error_without_touching_docker():
    plugin = ToutatisPlugin()
    findings = await plugin.run("this is not a username!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_run_passes_session_id_via_env_not_argv(monkeypatch):
    captured = {}

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        captured["args"] = args
        captured["env"] = env
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"profile": {}, "lookup": {}}', stderr=b"", error=None)

    monkeypatch.setattr(toutatis_plugin, "run_hardened", fake_run_hardened)

    plugin = ToutatisPlugin()
    await plugin.run("alice", {"session_id": "super-secret-cookie"})

    assert captured["args"] == ["alice"]
    assert captured["env"] == {"IG_SESSIONID": "super-secret-cookie"}


async def test_run_omits_env_when_no_session_id(monkeypatch):
    captured = {}

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        captured["env"] = env
        return DockerRunResult(ok=True, returncode=0, stdout=b'{"profile": {}, "lookup": {}}', stderr=b"", error=None)

    monkeypatch.setattr(toutatis_plugin, "run_hardened", fake_run_hardened)

    plugin = ToutatisPlugin()
    await plugin.run("alice")

    assert captured["env"] is None


def test_parse_result_user_not_found_is_not_found():
    plugin = ToutatisPlugin()
    data = {"profile": {"id": None, "error": "User not found"}, "lookup": {}}

    findings = plugin._parse_result("alice", data)

    assert findings[0].status == Status.NOT_FOUND


def test_parse_result_rate_limit_is_error_not_not_found():
    plugin = ToutatisPlugin()
    data = {"profile": {"id": None, "error": "Rate limit"}, "lookup": {}}

    findings = plugin._parse_result("alice", data)

    assert findings[0].status == Status.ERROR
    assert "Rate limit" in findings[0].evidence["reason"]


def test_parse_result_found_with_full_profile():
    plugin = ToutatisPlugin()
    data = {
        "profile": {
            "user": {
                "full_name": "Alice Example",
                "is_verified": True,
                "is_private": False,
                "follower_count": 1000,
                "biography": "hello",
                "hd_profile_pic_url_info": {"url": "https://example.com/pic.jpg"},
            },
            "error": None,
        },
        "lookup": {"user": {"obfuscated_email": "a****e@example.com"}, "error": None},
    }

    findings = plugin._parse_result("alice", data)

    assert findings[0].status == Status.FOUND
    assert findings[0].url == "https://www.instagram.com/alice/"
    assert findings[0].evidence["profile"]["fullname"] == "Alice Example"
    assert findings[0].evidence["obfuscated_email"] == "a****e@example.com"
    assert findings[0].evidence["profile"]["image"] == "https://example.com/pic.jpg"
    assert findings[0].evidence["headline"] == "Alice Example · obfuscated contact recovered"


def test_parse_result_redacted_profile_without_session_gets_honest_headline():
    plugin = ToutatisPlugin()
    data = {
        "profile": {"user": {"id": "123", "username": "alice", "profile_pic_url": "https://example.com/p.jpg"}, "error": None},
        "lookup": {"user": {"message": "", "status": "fail"}, "error": None},
    }

    findings = plugin._parse_result("alice", data)

    assert findings[0].status == Status.FOUND
    assert "limited data without a session cookie" in findings[0].evidence["headline"]
    assert findings[0].evidence["profile"]["image"] == "https://example.com/p.jpg"
    assert "obfuscated_email" not in findings[0].evidence


def test_parse_result_no_user_and_no_confirmed_absent_error_is_error():
    plugin = ToutatisPlugin()
    data = {"profile": {"user": None, "error": "Not found"}, "lookup": {}}

    findings = plugin._parse_result("alice", data)

    assert findings[0].status == Status.ERROR


async def test_run_reports_error_on_bad_json(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b"not json", stderr=b"", error=None)

    monkeypatch.setattr(toutatis_plugin, "run_hardened", fake_run_hardened)

    plugin = ToutatisPlugin()
    findings = await plugin.run("alice")

    assert findings[0].status == Status.ERROR
    assert "parseable JSON" in findings[0].evidence["reason"]


async def test_run_reports_docker_failure(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=1, stdout=b"", stderr=b"boom", error=None)

    monkeypatch.setattr(toutatis_plugin, "run_hardened", fake_run_hardened)

    plugin = ToutatisPlugin()
    findings = await plugin.run("alice")

    assert findings[0].status == Status.ERROR
    assert "docker run failed" in findings[0].evidence["reason"]


def test_parse_result_dumps_roundtrip_smoke():
    # Sanity: whatever _parse_result receives must at least be valid JSON
    # shaped like what the real driver script prints.
    raw = '{"profile": {"user": {"full_name": "X"}, "error": null}, "lookup": {"error": "rate limit"}}'
    data = json.loads(raw)
    plugin = ToutatisPlugin()

    findings = plugin._parse_result("x", data)

    assert findings[0].status == Status.FOUND
