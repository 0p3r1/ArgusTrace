import httpx
import pytest

from argustrace import versioning
from argustrace.versioning import VersionStatus


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    """Patch httpx.AsyncClient globally so each test supplies its own handler."""
    handler_holder = {}

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = _mock_transport(handler_holder["handler"])
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)
    return handler_holder


async def test_check_pypi_current(_patch_client):
    def handler(request):
        return httpx.Response(200, json={"releases": {"1.0.0": [], "1.1.0": [], "1.2.0": []}})

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "1.2.0")
    assert result.status == VersionStatus.CURRENT
    assert result.latest == "1.2.0"


async def test_check_pypi_behind_one_release(_patch_client):
    def handler(request):
        return httpx.Response(200, json={"releases": {"1.0.0": [], "1.1.0": [], "1.2.0": []}})

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "1.1.0")
    assert result.status == VersionStatus.BEHIND


async def test_check_pypi_outdated_multiple_releases_behind(_patch_client):
    def handler(request):
        return httpx.Response(200, json={"releases": {"1.0.0": [], "1.1.0": [], "1.2.0": []}})

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "1.0.0")
    assert result.status == VersionStatus.OUTDATED


async def test_check_pypi_unknown_when_pinned_not_in_release_list(_patch_client):
    def handler(request):
        return httpx.Response(200, json={"releases": {"1.0.0": [], "1.1.0": []}})

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "0.9.9-yanked")
    assert result.status == VersionStatus.UNKNOWN


async def test_check_pypi_unknown_on_http_error(_patch_client):
    def handler(request):
        return httpx.Response(500)

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "1.0.0")
    assert result.status == VersionStatus.UNKNOWN
    assert result.detail is not None


async def test_check_pypi_unknown_on_network_error(_patch_client):
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    _patch_client["handler"] = handler
    result = await versioning.check_pypi("sometool", "1.0.0")
    assert result.status == VersionStatus.UNKNOWN


async def test_check_dockerhub_filters_out_latest_tag(_patch_client):
    def handler(request):
        return httpx.Response(200, json={"results": [
            {"name": "latest"}, {"name": "2.0.0"}, {"name": "1.0.0"},
        ]})

    _patch_client["handler"] = handler
    result = await versioning.check_dockerhub("some/repo", "2.0.0")
    assert result.status == VersionStatus.CURRENT
    assert result.latest == "2.0.0"


async def test_check_github_releases_current(_patch_client):
    def handler(request):
        return httpx.Response(200, json=[
            {"tag_name": "4.11.1", "draft": False},
            {"tag_name": "4.11.0", "draft": False},
        ])

    _patch_client["handler"] = handler
    result = await versioning.check_github_releases("some/repo", "4.11.1")
    assert result.status == VersionStatus.CURRENT


async def test_check_github_releases_falls_back_to_tags_when_no_releases(_patch_client):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{"name": "v2.0"}, {"name": "v1.0"}])

    _patch_client["handler"] = handler
    result = await versioning.check_github_releases("some/repo", "v2.0")
    assert result.status == VersionStatus.CURRENT
    assert any(c.endswith("/tags") for c in calls)


async def test_check_github_releases_tags_fallback_requests_per_page_100(_patch_client):
    # Regression: without an explicit per_page, GitHub's tags endpoint
    # defaults to 30 — verified live against exiftool/exiftool, where our
    # pinned version sat just past that default page, past every real
    # release since, producing a false "unknown" instead of "outdated".
    captured = {}

    def handler(request):
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[])
        captured["per_page"] = request.url.params.get("per_page")
        return httpx.Response(200, json=[{"name": "v2.0"}, {"name": "v1.0"}])

    _patch_client["handler"] = handler
    await versioning.check_github_releases("some/repo", "v2.0")

    assert captured["per_page"] == "100"


async def test_check_dispatches_none_without_network_call():
    result = await versioning.check("crtsh", {"method": "none"})
    assert result.status == VersionStatus.NOT_APPLICABLE
