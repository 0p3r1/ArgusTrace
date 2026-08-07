import json

from typer.testing import CliRunner

from argustrace.cli import _build_options, app

runner = CliRunner()


def test_investigate_mock_plugin_prints_findings_json():
    result = runner.invoke(app, ["investigate", "alice"])
    assert result.exit_code == 0
    findings = json.loads(result.output)
    assert len(findings) == 2
    assert {f["status"] for f in findings} == {"FOUND", "NOT_FOUND"}


def test_investigate_rejects_unknown_plugin():
    result = runner.invoke(app, ["investigate", "alice", "--plugin", "not-a-plugin"])
    assert result.exit_code != 0
    assert "unknown plugin" in result.output


def test_investigate_rejects_unknown_option_name():
    result = runner.invoke(app, ["investigate", "alice", "--plugin", "maigret", "-o", "bogus=1"])
    assert result.exit_code != 0
    # Typer renders errors in a Rich box that hard-wraps, so assert on words
    # rather than a phrase that a line break can split.
    output = " ".join(result.output.split())
    assert "bogus" in output
    assert "accepted" in output
    for known in ("timeout", "retries", "tags", "enrich"):
        assert known in output


def test_investigate_rejects_malformed_option_pair():
    result = runner.invoke(app, ["investigate", "alice", "--plugin", "maigret", "-o", "no-equals-sign"])
    assert result.exit_code != 0
    assert "expected name=value" in result.output


def test_options_lists_all_families_when_no_plugin_given():
    result = runner.invoke(app, ["options"])
    assert result.exit_code == 0
    assert "maigret: Maigret" in result.output
    assert "sherlock: Sherlock" in result.output
    # the hidden mock/demo family is never listed
    assert "mock" not in result.output


def test_options_lists_a_families_options():
    result = runner.invoke(app, ["options", "maigret"])
    assert result.exit_code == 0
    assert "timeout (int, flag --timeout" in result.output
    assert "enrich (bool, flag --enrich" in result.output


def test_options_reports_no_options_for_crtsh():
    result = runner.invoke(app, ["options", "crtsh"])
    assert result.exit_code == 0
    assert "no configurable options" in result.output


def test_build_options_coerces_int_bool_and_enum_multi():
    options = _build_options("maigret", ["timeout=45", "enrich=true"])
    assert options == {"timeout": 45, "enrich": True}

    options = _build_options("theharvester", ["sources=rapiddns,crtsh"])
    assert options == {"sources": ["rapiddns", "crtsh"]}


def test_build_options_bool_false_variants_are_falsy():
    for raw in ["false", "0", "no", ""]:
        assert _build_options("maigret", [f"enrich={raw}"]) == {"enrich": False}


def test_build_options_empty_pairs_returns_empty_dict():
    assert _build_options("maigret", []) == {}
