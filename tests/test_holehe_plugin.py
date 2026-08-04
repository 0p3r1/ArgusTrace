import json

from argustrace.core.models import Status
from argustrace.plugins import holehe_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.holehe_plugin import HolehePlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = HolehePlugin()
    findings = await plugin.run("not-an-email")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_rows_maps_ratelimit_and_exists_onto_status():
    plugin = HolehePlugin()
    rows = [
        {"name": "github", "domain": "github.com", "method": "login", "frequent_rate_limit": False,
         "rateLimit": True, "exists": False, "emailrecovery": None, "phoneNumber": None, "others": None},
        {"name": "adobe", "domain": "adobe.com", "method": "password recovery", "frequent_rate_limit": False,
         "rateLimit": False, "exists": True, "emailrecovery": None, "phoneNumber": None, "others": None},
        {"name": "amazon", "domain": "amazon.com", "method": "login", "frequent_rate_limit": False,
         "rateLimit": False, "exists": False, "emailrecovery": None, "phoneNumber": None, "others": None},
    ]

    findings = plugin._parse_rows("alice@example.com", rows)

    by_source = {f.source: f for f in findings}
    assert len(findings) == 3
    # rateLimit=True takes priority over exists, regardless of its value.
    assert by_source["holehe:github"].status == Status.ERROR
    assert by_source["holehe:adobe"].status == Status.FOUND
    assert by_source["holehe:amazon"].status == Status.NOT_FOUND
    assert by_source["holehe:adobe"].evidence["headline"] == "adobe.com · password recovery"


def test_parse_rows_headline_prefers_extracted_fullname_over_domain_method():
    plugin = HolehePlugin()
    rows = [{
        "name": "somesite", "domain": "somesite.com", "method": "register", "frequent_rate_limit": False,
        "rateLimit": False, "exists": True, "emailrecovery": None, "phoneNumber": None,
        "others": {"FullName": "Alice Example"},
    }]

    findings = plugin._parse_rows("alice@example.com", rows)

    assert findings[0].evidence["headline"] == "Alice Example"
    assert findings[0].evidence["profile"] == {"FullName": "Alice Example"}


def test_parse_rows_surfaces_recovery_hint():
    plugin = HolehePlugin()
    rows = [{
        "name": "somesite", "domain": "somesite.com", "method": "register", "frequent_rate_limit": False,
        "rateLimit": False, "exists": True, "emailrecovery": "a***@gmail.com", "phoneNumber": None, "others": None,
    }]

    findings = plugin._parse_rows("alice@example.com", rows)

    assert findings[0].evidence["recovery_hint"] == {"email": "a***@gmail.com"}


def test_build_args_no_password_recovery_off_by_default():
    plugin = HolehePlugin()
    args = plugin._build_args("alice@example.com", {})
    assert "-NP" not in args


def test_build_args_no_password_recovery_flag():
    plugin = HolehePlugin()
    args = plugin._build_args("alice@example.com", {"no_password_recovery": True})
    assert "-NP" in args


def test_build_args_passes_timeout_to_the_wrapper():
    # Holehe's own --timeout is unusable (v1.61 stores it as a string), so
    # this is our wrapper's httpx timeout, passed positionally.
    plugin = HolehePlugin()
    assert plugin._build_args("alice@example.com", {}) == ["alice@example.com", "10"]
    assert plugin._build_args("alice@example.com", {"timeout": 25})[1] == "25"


def test_resolve_timeout_clamps_and_ignores_invalid_values():
    plugin = HolehePlugin()
    assert plugin._resolve_timeout({"timeout": 999}) == 30
    assert plugin._resolve_timeout({"timeout": 1}) == 5
    assert plugin._resolve_timeout({"timeout": "not-a-number"}) == 10


async def test_run_reports_docker_failure(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=False, returncode=None, stdout=b"", stderr=b"", error="docker not available")

    monkeypatch.setattr(holehe_plugin, "run_hardened", fake_run_hardened)

    plugin = HolehePlugin()
    findings = await plugin.run("alice@example.com")

    assert findings[0].status == Status.ERROR
    assert "docker not available" in findings[0].evidence["reason"]


async def test_run_reports_nonzero_exit(monkeypatch):
    # This is the exact failure mode holehe's own check_update() used to
    # cause on every invocation once a newer PyPI release existed — the
    # wrapper script bypasses that entirely, but a crash for any other
    # reason must still surface as ERROR, not silently produce no findings.
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=1, stdout=b"", stderr=b"Traceback: crashed", error=None)

    monkeypatch.setattr(holehe_plugin, "run_hardened", fake_run_hardened)

    plugin = HolehePlugin()
    findings = await plugin.run("alice@example.com")

    assert findings[0].status == Status.ERROR
    assert "holehe run failed" in findings[0].evidence["reason"]


async def test_run_reports_unparseable_json(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        return DockerRunResult(ok=True, returncode=0, stdout=b"not json", stderr=b"", error=None)

    monkeypatch.setattr(holehe_plugin, "run_hardened", fake_run_hardened)

    plugin = HolehePlugin()
    findings = await plugin.run("alice@example.com")

    assert findings[0].status == Status.ERROR
    assert "no parseable JSON" in findings[0].evidence["reason"]


async def test_run_parses_real_shaped_output(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        stdout = json.dumps([
            {"name": "twitter", "domain": "twitter.com", "method": "register", "frequent_rate_limit": False,
             "rateLimit": False, "exists": True, "emailrecovery": None, "phoneNumber": None, "others": None},
        ]).encode()
        return DockerRunResult(ok=True, returncode=0, stdout=stdout, stderr=b"", error=None)

    monkeypatch.setattr(holehe_plugin, "run_hardened", fake_run_hardened)

    plugin = HolehePlugin()
    findings = await plugin.run("alice@example.com")

    assert findings[0].status == Status.FOUND
    assert findings[0].source == "holehe:twitter"
