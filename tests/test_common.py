"""Tests for the helpers shared across plugins."""

import re

from argustrace.core.models import Status
from argustrace.plugins import _common
from argustrace.plugins._common import (
    DOMAIN_PATTERN_SOURCE,
    USERNAME_PATTERN_SOURCE,
    clamp_int,
    error_finding,
    fetch_json,
)

DOMAIN = re.compile(DOMAIN_PATTERN_SOURCE)
USERNAME = re.compile(USERNAME_PATTERN_SOURCE)


def test_domain_pattern_accepts_real_domains():
    for good in ("example.com", "a.b.example.co.uk", "xn--bcher-kva.example"):
        assert DOMAIN.match(good), good


def test_domain_pattern_rejects_non_domains():
    for bad in ("not a domain", "http://example.com", "example", "-bad.com", "example.123"):
        assert not DOMAIN.match(bad), bad


def test_username_pattern_bounds():
    assert USERNAME.match("torvalds")
    assert USERNAME.match("a.b-c_d")
    assert not USERNAME.match("has space")
    assert not USERNAME.match("x" * 65)


def test_error_finding_is_always_error_with_a_reason():
    finding = error_finding("x", entity_type="domain", source="crt.sh", reason="boom")

    assert finding.status == Status.ERROR
    assert finding.entity_type == "domain"
    assert finding.source == "crt.sh"
    assert finding.evidence == {"reason": "boom"}


def test_error_finding_keeps_extra_evidence():
    finding = error_finding("x", entity_type="ip", source="rdap", reason="boom", http_status=500)
    assert finding.evidence["http_status"] == 500


def test_clamp_int_clamps_and_falls_back():
    assert clamp_int(20, default=10, low=5, high=30) == 20
    assert clamp_int(999, default=10, low=5, high=30) == 30
    assert clamp_int(1, default=10, low=5, high=30) == 5
    assert clamp_int("nope", default=10, low=5, high=30) == 10
    assert clamp_int(None, default=10, low=5, high=30) == 10


async def _instant(_seconds):
    return None


async def test_fetch_json_returns_parsed_data(monkeypatch, fake_docker, docker_result):
    fake_docker(_common, docker_result(b'{"a": 1}'))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc")

    assert fetched.error is None
    assert fetched.data == {"a": 1}


async def test_fetch_json_uses_the_shared_curl_image_and_passes_extra_args(fake_docker, docker_result):
    calls = fake_docker(_common, docker_result(b"[]"))
    await fetch_json("https://x", timeout_s=5, describe="svc", extra_args=("-L", "-H", "Accept: x"))

    assert calls[0].image.startswith("argustrace-curl")
    assert calls[0].args == ["-L", "-H", "Accept: x", "https://x"]


async def test_fetch_json_reports_docker_failure(fake_docker, docker_result):
    fake_docker(_common, docker_result(ok=False, returncode=None, error="docker missing"))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc")

    assert fetched.data is None
    assert fetched.error == "docker missing"


async def test_fetch_json_reports_curl_failure(fake_docker, docker_result):
    fake_docker(_common, docker_result(b"", returncode=1, stderr=b"boom"))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc")

    assert "curl failed" in fetched.error


async def test_fetch_json_reports_non_json(fake_docker, docker_result):
    fake_docker(_common, docker_result(b"<html>"))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc")

    assert "svc returned a non-JSON or empty response" == fetched.error


async def test_fetch_json_guards_the_shape(fake_docker, docker_result):
    """Valid JSON is not the same as the JSON we can parse: crt.sh answers
    with an error object where the API normally returns an array."""
    fake_docker(_common, docker_result(b'{"error": "busy"}'))
    fetched = await fetch_json("https://x", timeout_s=5, describe="crt.sh", expect=list)

    assert fetched.data is None
    assert "unexpected JSON shape" in fetched.error


async def test_fetch_json_retries_then_succeeds(monkeypatch, fake_docker, docker_result):
    monkeypatch.setattr(_common.asyncio, "sleep", _instant)
    calls = fake_docker(
        _common,
        docker_result(b"", returncode=1, stderr=b"502"),
        docker_result(b"[]"),
    )
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc", attempts=2)

    assert len(calls) == 2
    assert fetched.data == []


async def test_fetch_json_gives_up_reporting_the_attempt_count(monkeypatch, fake_docker, docker_result):
    monkeypatch.setattr(_common.asyncio, "sleep", _instant)
    calls = fake_docker(_common, docker_result(b"", returncode=1, stderr=b"502"))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc", attempts=3)

    assert len(calls) == 3
    assert fetched.data is None
    assert "after 3 attempts" in fetched.error


async def test_fetch_json_single_attempt_has_no_attempt_suffix(fake_docker, docker_result):
    fake_docker(_common, docker_result(b"", returncode=1, stderr=b"boom"))
    fetched = await fetch_json("https://x", timeout_s=5, describe="svc")

    assert "attempts" not in fetched.error
