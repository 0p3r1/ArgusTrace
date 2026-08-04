from fastapi.testclient import TestClient

from argustrace.api import app
from argustrace.plugins import registry

client = TestClient(app)


def test_list_plugins_includes_native_reports():
    res = client.get("/api/plugins")
    assert res.status_code == 200
    by_family = {f["family"]: f for f in res.json()}

    maigret_reports = {r["format"]: r for r in by_family["maigret"]["native_reports"]}
    assert maigret_reports["html"]["available"] is True
    assert maigret_reports["html"]["kind"] == "download"
    assert maigret_reports["pdf"]["available"] is False

    assert by_family["ignorant"]["native_reports"] == []


def test_get_native_report_unknown_family():
    res = client.get("/api/tools/bogus/report", params={"entity": "alice", "format": "html"})
    assert res.status_code == 404


def test_get_native_report_unsupported_format():
    res = client.get("/api/tools/maigret/report", params={"entity": "alice", "format": "xml"})
    assert res.status_code == 404


def test_get_native_report_unavailable_format():
    res = client.get("/api/tools/maigret/report", params={"entity": "alice", "format": "pdf"})
    assert res.status_code == 400
    assert "optional 'pdf' extra" in res.json()["detail"]


def test_get_native_report_link_kind_is_not_downloadable():
    res = client.get("/api/tools/crtsh/report", params={"entity": "example.com", "format": "html"})
    assert res.status_code == 404


def test_get_native_report_success(monkeypatch):
    async def fake_generate_report(entity: str, report_format: str, plugin: str | None = None) -> bytes:
        assert entity == "alice"
        assert report_format == "html"
        return b"<html>fake report</html>"

    monkeypatch.setitem(registry.NATIVE_REPORT_GENERATORS, "maigret", fake_generate_report)

    res = client.get("/api/tools/maigret/report", params={"entity": "alice", "format": "html"})
    assert res.status_code == 200
    assert res.content == b"<html>fake report</html>"
    assert res.headers["content-type"].startswith("text/html")
    assert 'filename="maigret_alice.html"' in res.headers["content-disposition"]


def test_get_native_report_generator_raises_value_error_becomes_400(monkeypatch):
    async def failing_generate_report(entity: str, report_format: str, plugin: str | None = None) -> bytes:
        raise ValueError("invalid entity: nope")

    monkeypatch.setitem(registry.NATIVE_REPORT_GENERATORS, "maigret", failing_generate_report)

    res = client.get("/api/tools/maigret/report", params={"entity": "not valid", "format": "html"})
    assert res.status_code == 400
    assert "invalid entity" in res.json()["detail"]


def test_get_native_report_unknown_plugin_is_404():
    res = client.get(
        "/api/tools/theharvester/report",
        params={"entity": "example.com", "format": "xml", "plugin": "bogus-plugin"},
    )
    assert res.status_code == 404


def test_get_native_report_threads_plugin_variant_to_generator(monkeypatch):
    # Regression: theHarvester's XML report used to always regenerate with
    # the fast/single-source scan regardless of which variant the results
    # being previewed actually came from — the `plugin` query param (the
    # exact scan variant, e.g. "theharvester-broad") must reach the generator.
    captured = {}

    async def fake_generate_report(entity: str, report_format: str, plugin: str | None = None) -> bytes:
        captured["plugin"] = plugin
        return b"<xml/>"

    monkeypatch.setitem(registry.NATIVE_REPORT_GENERATORS, "theharvester", fake_generate_report)

    res = client.get(
        "/api/tools/theharvester/report",
        params={"entity": "example.com", "format": "xml", "plugin": "theharvester-broad"},
    )
    assert res.status_code == 200
    assert captured["plugin"] == "theharvester-broad"
