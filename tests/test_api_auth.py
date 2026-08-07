"""Auth and binding guards around the API.

Reaching this API means being able to run containers and make the host fetch
arbitrary URLs, so these two guards are what keep it from being an open
remote-execution surface if it is ever exposed.
"""

from dataclasses import replace

import pytest
import typer
from fastapi.testclient import TestClient

from argustrace import api, cli
from argustrace.api import TOKEN_HEADER, app
from argustrace.settings import SETTINGS


def test_no_token_configured_means_no_auth_required():
    """The default is loopback-only local use; a mandatory secret there would
    be friction with nothing to protect against."""
    with TestClient(app) as client:
        assert client.get("/api/plugins").status_code == 200


def test_configured_token_is_required(monkeypatch):
    monkeypatch.setattr(api, "SETTINGS", replace(SETTINGS, api_token="s3cret"))
    with TestClient(app) as client:
        assert client.get("/api/plugins").status_code == 401


def test_configured_token_accepts_the_right_value(monkeypatch):
    monkeypatch.setattr(api, "SETTINGS", replace(SETTINGS, api_token="s3cret"))
    with TestClient(app) as client:
        res = client.get("/api/plugins", headers={TOKEN_HEADER: "s3cret"})
        assert res.status_code == 200


def test_configured_token_rejects_a_wrong_value(monkeypatch):
    monkeypatch.setattr(api, "SETTINGS", replace(SETTINGS, api_token="s3cret"))
    with TestClient(app) as client:
        res = client.get("/api/plugins", headers={TOKEN_HEADER: "wrong"})
        assert res.status_code == 401


def test_investigate_is_also_gated(monkeypatch):
    """Auth is applied app-wide, not per-route, so a new endpoint cannot
    silently ship unauthenticated."""
    monkeypatch.setattr(api, "SETTINGS", replace(SETTINGS, api_token="s3cret"))
    with TestClient(app) as client:
        res = client.post("/api/investigate", json={"entity": "alice", "plugin": "mock"})
        assert res.status_code == 401


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_serve_allows_loopback_without_a_token(monkeypatch, host):
    started = {}
    monkeypatch.setattr(cli, "SETTINGS", replace(SETTINGS, api_token=None))
    monkeypatch.setitem(
        __import__("sys").modules, "uvicorn",
        type("FakeUvicorn", (), {"run": staticmethod(lambda *a, **k: started.update(k))}),
    )

    cli.serve(host=host, port=8000)
    assert started["host"] == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_serve_refuses_a_reachable_address_without_a_token(monkeypatch, host):
    monkeypatch.setattr(cli, "SETTINGS", replace(SETTINGS, api_token=None))

    with pytest.raises(typer.BadParameter) as excinfo:
        cli.serve(host=host, port=8000)
    assert "without authentication" in str(excinfo.value)


def test_serve_allows_a_reachable_address_once_a_token_is_set(monkeypatch):
    started = {}
    monkeypatch.setattr(cli, "SETTINGS", replace(SETTINGS, api_token="s3cret"))
    monkeypatch.setitem(
        __import__("sys").modules, "uvicorn",
        type("FakeUvicorn", (), {"run": staticmethod(lambda *a, **k: started.update(k))}),
    )

    cli.serve(host="0.0.0.0", port=8000)
    assert started["host"] == "0.0.0.0"
