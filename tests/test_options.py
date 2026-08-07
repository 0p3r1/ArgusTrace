"""Option validation at the API/CLI boundary."""

import pytest

from argustrace.plugins.options import OptionError, family_of_plugin, validate


def test_family_of_plugin_resolves_variants():
    assert family_of_plugin("maigret-full") == "maigret"
    assert family_of_plugin("sherlock") == "sherlock"
    assert family_of_plugin("nope") is None


def test_unknown_plugin_is_refused():
    with pytest.raises(OptionError, match="unknown plugin"):
        validate("nope", {})


def test_no_options_is_fine():
    assert validate("maigret", None) == {}
    assert validate("maigret", {}) == {}


def test_unknown_option_names_are_listed_with_the_accepted_ones():
    with pytest.raises(OptionError) as excinfo:
        validate("maigret", {"bogus": 1, "alsobad": 2})
    message = str(excinfo.value)
    assert "alsobad, bogus" in message
    assert "timeout" in message  # the accepted list


def test_integers_are_coerced_from_strings():
    """The CLI passes everything as text; the API passes real types."""
    assert validate("maigret", {"timeout": "45"}) == {"timeout": 45}
    assert validate("maigret", {"timeout": 45}) == {"timeout": 45}


def test_out_of_range_integer_is_refused_not_clamped():
    """Sherlock used to clamp 999 to 30 without telling anyone — the user
    asked for one thing and silently got another."""
    with pytest.raises(OptionError) as excinfo:
        validate("sherlock", {"timeout": 999})
    assert "outside the accepted range" in str(excinfo.value)
    assert "5..30" in str(excinfo.value)


def test_unparseable_integer_is_refused_not_dropped():
    """recherche-entreprises used to silently drop a bad int, losing the
    filter while still returning results as though it had applied."""
    with pytest.raises(OptionError, match="expected an integer"):
        validate("recherche-entreprises", {"ca_min": "lots"})


def test_boolean_accepts_real_bools_and_text():
    assert validate("sherlock", {"nsfw": True}) == {"nsfw": True}
    assert validate("sherlock", {"nsfw": "true"}) == {"nsfw": True}
    assert validate("sherlock", {"nsfw": "no"}) == {"nsfw": False}
    assert validate("sherlock", {"nsfw": ""}) == {"nsfw": False}


def test_boolean_rejects_nonsense():
    with pytest.raises(OptionError, match="expected true or false"):
        validate("sherlock", {"nsfw": "yolo"})


def test_enum_must_be_one_of_the_declared_choices():
    assert validate("recherche-entreprises", {"etat_administratif": "A"}) == {"etat_administratif": "A"}
    with pytest.raises(OptionError, match="not one of"):
        validate("recherche-entreprises", {"etat_administratif": "Z"})


def test_enum_multi_accepts_a_list_or_a_comma_separated_string():
    assert validate("theharvester", {"sources": ["otx", "crtsh"]})["sources"] == ["otx", "crtsh"]
    assert validate("theharvester", {"sources": "otx,crtsh"})["sources"] == ["otx", "crtsh"]


def test_enum_multi_rejects_values_outside_the_choices():
    with pytest.raises(OptionError, match="not among"):
        validate("theharvester", {"sources": ["otx", "shodan"]})


def test_explicit_null_means_unset_not_invalid():
    """The web form clears a field by sending null; that is not a bad value."""
    assert validate("maigret", {"tags": None}) == {}


def test_secret_values_are_never_echoed_in_errors():
    """A rejected session cookie must not come back in the error message."""
    with pytest.raises(OptionError) as excinfo:
        validate("toutatis", {"session_id": "abc", "bogus": "x"})
    assert "abc" not in str(excinfo.value)


def test_secret_is_passed_through_as_text():
    assert validate("toutatis", {"session_id": "abc123"}) == {"session_id": "abc123"}
